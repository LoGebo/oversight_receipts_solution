"""Transaction pattern rules: TIME-01 (overnight), TIME-02 (no trip), TIME-03 (split), TIME-04 (weekend off-trip).

TIME-01, TIME-02 and TIME-04 are review signals, never exceptions; TIME-03 is a high exception.
Clock: transaction_datetime as written, the local time at the merchant, with no time zone conversion
(an offset, if one were ever written, is ignored: the wall-clock time decides). A receipt with no date
gets not_applicable for TIME-01, TIME-03 and TIME-04 (DOC-02 reports the missing date); an
unparseable one raises ValueError. A date with no time of day is not_applicable for TIME-01.
  TIME-01  00:00 <= time < 05:00.
  TIME-02  declared Meals - Individual, Lodging or Travel - Other with no trip_id.
  TIME-03  cross-receipt: run over one employee's day (common.day_key), grouped inside it by group_key,
           which adds merchant_name (stripped, casefolded). In a group of two or more, a split around a
           threshold is when every receipt it measures is at or below it and their sum is strictly above it:
             itemization  every receipt in the group is non-itemized: total_amount_usd vs $75 (DOC-01)
             meal cap     the group's meal receipts, per person as in MEAL-01, vs the employee's cap:
                          $60 APAC (REG-02), EUR 70 at the euro rate EMEA (REG-03), else $75 domestic or
                          $100 international (MEAL-01), the day's cap: the highest over the
                          employee's meal receipts that date, at any merchant
             gift cap     client gift lines naming the same recipient (gift_for hook) vs $50 (GIFT-01)
           TIME-03 fires on every receipt a split measures and cites no lines (EXC-04). It replaces the
           rule it splits around: the engine reports MEAL-01/REG-02/REG-03 of those receipts as
           superseded. DOC-01 and GIFT-01 need no such step: each receipt is at or below their
           threshold, so the split itself never breaches them on any one receipt.
  TIME-04  a Saturday or Sunday outside the trip's `trip_start`..`trip_end` (ISO dates on the receipt).
           The data's trip records hold no dates, so on it TIME-04 is always not_applicable.
With the day's cap, a meal-cap split always breaches the cap rule on its receipts, which is what TIME-03
replaces; a meal elsewhere that day keeps its own cap-rule breach. When the day's cap cannot be known (no
euro rate, or no home currency for the country), TIME-03 on the receipts it would measure is an ERR-TIME-03
review signal, unless a split around another threshold already fires it.
"""
from collections import defaultdict
from datetime import date, datetime
from fractions import Fraction

from validator.check import Check
from validator.rules.common import currency, day_key, itemized, meal_per_person, money
from validator.rules.documentation import ITEMIZE_ABOVE
from validator.rules.gifts import CAP as GIFT_CAP
from validator.rules.gifts import NOT_GIFTS
from validator.rules.meals import APAC_CAP, DOMESTIC_CAP, HOME_CURRENCY, INTERNATIONAL_CAP
from validator.rules.regional import REG03_CAP_EUR, _eur_rate

OVERNIGHT_UNTIL = 5  # hour: TIME-01 is 00:00 up to, not including, 05:00
TRAVEL_TYPES = ("Meals - Individual", "Lodging", "Travel - Other")
MEAL_CAP_RULES = ("MEAL-01", "REG-02", "REG-03")
RULE_IDS = ("TIME-01", "TIME-02", "TIME-03", "TIME-04")


def _when(receipt: dict) -> datetime | None:
    when = receipt.get("transaction_datetime")
    if when is None or (isinstance(when, str) and not when.strip()):
        return None
    return datetime.fromisoformat(when)


def group_key(receipt: dict) -> tuple:
    """TIME-03's group; a receipt missing the employee, merchant name or date is a group of its own."""
    emp, name, when = receipt.get("employee_id"), receipt.get("merchant_name"), receipt.get("transaction_datetime")
    if emp is None or not all(isinstance(x, str) and x.strip() for x in (name, when)):
        return ("receipt", receipt["receipt_id"])
    return (emp, name.strip().casefold(), when[:10])


def _meal_cap(receipt: dict, eur_usd: float | None) -> Fraction | None:
    """None when the cap turns on a missing euro rate or a country with no known home currency."""
    if receipt["entity"] == "APAC":
        return Fraction(APAC_CAP)
    if receipt["entity"] == "EMEA":
        rate = _eur_rate(receipt, eur_usd)
        return None if rate is None else Fraction(REG03_CAP_EUR * rate)
    home = HOME_CURRENCY.get(receipt["employee_country"])
    if home is None:
        return None
    return Fraction(DOMESTIC_CAP if currency(receipt) == home else INTERNATIONAL_CAP)


def _splits(group: list[dict], day: list[dict], categories: dict[str, str], gift_for: dict,
            eur_usd: dict[str, float | None]) -> tuple[dict[str, dict[str, str]], set[str]]:
    """(receipt_id -> {threshold: the numbers} for every split in a group of two or more receipts of `day`,
    the receipts whose meal-cap test cannot be run because the day's cap is unknown)."""
    found, unknown = defaultdict(dict), set()

    def test(threshold: str, label: str, amounts: dict[str, Fraction], cap: Fraction) -> None:
        total = sum(amounts.values(), Fraction(0))
        if all(a <= cap for a in amounts.values()) and total > cap:
            shown = (f"{label}: {' + '.join(f'${a:.2f} ({rid})' for rid, a in amounts.items())} = ${total:.2f}"
                     f" > ${cap:.2f}, each at or below it")
            for rid in amounts:
                found[rid][threshold] = shown

    if not any(itemized(r) for r in group):
        test("itemization", "non-itemized totals vs the $75 itemization threshold (DOC-01)",
             {r["receipt_id"]: Fraction(money(r["total_amount_usd"], "total_amount_usd")) for r in group},
             Fraction(ITEMIZE_ABOVE))
    per_person = {r["receipt_id"]: meal_per_person(r, categories) for r in group}
    meals = [r for r in group if per_person[r["receipt_id"]] is not None]
    if len(meals) > 1:
        day_meals = meals + [r for r in day if r not in group and meal_per_person(r, categories) is not None]
        caps = [_meal_cap(r, eur_usd.get(r["receipt_id"])) for r in day_meals]
        if None in caps:
            unknown.update(r["receipt_id"] for r in meals)
        else:
            test("meal cap", "meal spend per person vs the day's meal cap (MEAL-01, REG-02, REG-03)",
                 {r["receipt_id"]: per_person[r["receipt_id"]] for r in meals}, max(caps))
    gifts = defaultdict(lambda: defaultdict(Fraction))  # recipient -> receipt_id -> gift total
    for r in group:
        for li in r["line_items"]:
            kind, name = gift_for.get(li["line_id"], ("client", None))
            if kind == "client" and name and name.strip() and categories[li["line_id"]] not in NOT_GIFTS | {"gift_card"}:
                gifts[name.strip().casefold()][r["receipt_id"]] += Fraction(money(li["amount_usd"], li["line_id"]))
    for name, amounts in gifts.items():
        test("gift cap", f"gifts to {name} vs the $50 gift cap (GIFT-01)", dict(amounts), Fraction(GIFT_CAP))
    return found, unknown


def _time01(receipt: dict, when: datetime | None) -> Check:
    if when is None:
        return Check("TIME-01", "not_applicable", kind="signal", detail="no transaction time recorded (DOC-02)")
    if len(receipt["transaction_datetime"].strip()) <= len("2026-05-07"):
        return Check("TIME-01", "not_applicable", kind="signal", detail="a date with no time of day")
    shown = f"{when:%H:%M} local time at the merchant"
    if when.hour < OVERNIGHT_UNTIL:
        return Check("TIME-01", "fired", kind="signal", detail=f"{shown}: between 00:00 and 05:00")
    return Check("TIME-01", "not_fired", kind="signal", detail=shown)


def _time02(receipt: dict) -> Check:
    kind, trip = receipt["submitted_expense_type"], receipt.get("trip_id")
    if kind not in TRAVEL_TYPES:
        return Check("TIME-02", "not_applicable", kind="signal", detail=f"declared {kind!r}: not an individual travel expense")
    if trip is None or not str(trip).strip():
        return Check("TIME-02", "fired", kind="signal", detail=f"declared {kind!r} with no trip record")
    return Check("TIME-02", "not_fired", kind="signal", detail=f"declared {kind!r} on trip {trip}")


def _time04(receipt: dict, when: datetime | None) -> Check:
    start, end = receipt.get("trip_start"), receipt.get("trip_end")
    if receipt.get("trip_id") is None:
        return Check("TIME-04", "not_applicable", kind="signal", detail="no trip record (TIME-02 covers it)")
    if start is None or end is None:
        return Check("TIME-04", "not_applicable", kind="signal", detail="the trip record holds no start and end dates")
    if when is None:
        return Check("TIME-04", "not_applicable", kind="signal", detail="no transaction date recorded (DOC-02)")
    day, start, end = when.date(), date.fromisoformat(start), date.fromisoformat(end)
    if start > end:
        raise ValueError(f"trip_start {start} is after trip_end {end}")
    shown = f"{day:%A} {day} vs trip {start} to {end}"
    if day.weekday() >= 5 and not start <= day <= end:
        return Check("TIME-04", "fired", kind="signal", detail=f"{shown}: weekend, outside the trip")
    return Check("TIME-04", "not_fired", kind="signal", detail=shown)


def timing_checks(day: list[dict], categories: dict[str, str], gift_for: dict | None = None,
                  eur_usd: dict[str, float | None] | None = None) -> tuple[dict[str, list[Check]], dict[str, tuple[str, ...]]]:
    """(receipt_id -> [TIME-01..TIME-04] Checks, receipt_id -> the thresholds its TIME-03 split is around).

    `day` holds one employee's receipts of one calendar date (common.day_key). `categories` maps line_id ->
    category; `gift_for` is the gift recipient hook (gifts.py); `eur_usd` maps receipt_id -> euro rate for
    a non-EUR EMEA receipt.
    """
    if len({day_key(r) for r in day}) != 1:
        raise ValueError(f"one employee's day expected, got {sorted(map(str, {day_key(r) for r in day}))}")
    groups = defaultdict(list)
    for r in day:
        groups[group_key(r)].append(r)
    found, unknown = {}, set()
    for g in groups.values():
        if len(g) > 1:
            f, u = _splits(g, day, categories, gift_for or {}, eur_usd or {})
            found.update(f)
            unknown |= u
    out = {}
    for r in day:
        rid, when, key = r["receipt_id"], _when(r), group_key(r)
        if key[0] == "receipt":
            time03 = Check("TIME-03", "not_applicable", detail="no employee, merchant name or date to group by")
        elif rid in found:
            time03 = Check("TIME-03", "fired", severity="high", detail="split transaction: " + "; ".join(found[rid].values()))
        elif rid in unknown:
            time03 = Check("ERR-TIME-03", "fired", kind="signal",
                           detail="TIME-03: the day's meal cap is unknown (no euro rate, or no home currency for the "
                                  "employee's country), so a split around it cannot be ruled out")
        else:
            time03 = Check("TIME-03", "not_fired", detail=f"{len(groups[key])} receipt(s) by {key[0]} at {r['merchant_name']} "
                                                          f"on {key[2]}: no threshold split")
        out[rid] = [_time01(r, when), _time02(r), time03, _time04(r, when)]
    return out, {rid: tuple(f) for rid, f in found.items()}
