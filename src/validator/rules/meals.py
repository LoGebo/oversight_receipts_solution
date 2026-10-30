"""Meal rules: MEAL-01 (daily cap), MEAL-02 (attendee documentation) and REG-02 (APAC daily cap).

Cross-receipt, like health.py: a day's cap is over all of one employee's meal receipts that date.
Meal receipt, meal spend and per person are MEAL-01's definitions, in common.meal_per_person.
  per day       the per-person amounts of one employee's meal receipts on one calendar date, summed
                exactly (common.day_key). The date is transaction_datetime as written: local time at
                the merchant, no time zone conversion (a 02:14 breakfast counts on the date printed).
                A receipt with no employee_id or no date is a day of its own.
Caps (strictly above fires; exactly the cap passes): $75 domestic / $100 international, the higher
when a day mixes the two; APAC: $60 per person under REG-02, which supersedes MEAL-01.
EMEA: REG-03 (regional.py) replaces MEAL-01 there, so MEAL-01 is superseded here.
A breach is raised on every meal receipt that contributes to that day. MEAL-01, MEAL-02 and REG-02
are whole-receipt rules (EXC-04) and cite no lines.
Limit: refunds and negative amounts get no special handling here (the engine's ERR-input signal sends the
receipt to review); a negative line lowers the day's total.
"""
from collections import defaultdict
from decimal import Decimal
from fractions import Fraction

from validator.check import Check
from validator.rules.common import attendees, currency, day_key, meal_per_person, money

DOMESTIC_CAP, INTERNATIONAL_CAP = Decimal("75"), Decimal("100")
APAC_CAP = Decimal("60")
MEAL02_THRESHOLD = Decimal("150")                      # receipt total in USD, strictly above
# Home currency per employee country (ISO 3166 -> ISO 4217); only consulted for GLOBAL employees (APAC/EMEA use
# regional caps). An unknown country is never guessed: MEAL-01 alone becomes an ERR-MEAL-01 review signal.
HOME_CURRENCY = {
    "US": "USD", "CA": "CAD", "MX": "MXN", "BR": "BRL", "AR": "ARS", "CL": "CLP", "CO": "COP", "PE": "PEN",
    "GB": "GBP", "IE": "EUR", "FR": "EUR", "DE": "EUR", "ES": "EUR", "IT": "EUR", "NL": "EUR", "PT": "EUR",
    "BE": "EUR", "AT": "EUR", "FI": "EUR", "GR": "EUR", "LU": "EUR", "CH": "CHF", "SE": "SEK", "NO": "NOK",
    "DK": "DKK", "PL": "PLN", "IN": "INR", "JP": "JPY", "CN": "CNY", "SG": "SGD", "AU": "AUD", "NZ": "NZD",
    "KR": "KRW", "HK": "HKD", "TW": "TWD", "TH": "THB", "ID": "IDR", "MY": "MYR", "PH": "PHP", "VN": "VND",
    "AE": "AED", "SA": "SAR", "IL": "ILS", "ZA": "ZAR",
}
RULE_IDS = ("MEAL-01", "MEAL-02", "REG-02")


def meal_checks(receipts: list[dict], categories: dict[str, str]) -> dict[str, list[Check]]:
    """receipt_id -> [MEAL-01, MEAL-02, REG-02] Checks, for every receipt. `categories` maps
    line_id -> category over ALL receipts; a missing line raises KeyError."""
    per_person = {r["receipt_id"]: meal_per_person(r, categories) for r in receipts}
    meals = {r["receipt_id"]: r for r in receipts if per_person[r["receipt_id"]] is not None}
    days = defaultdict(list)  # day_key -> meal receipt ids
    for rid, r in meals.items():
        days[day_key(r)].append(rid)

    out = {}
    for r in receipts:
        rid, entity = r["receipt_id"], r["entity"]
        if rid not in meals:
            out[rid] = [Check(x, "not_applicable", detail="not a meal receipt") for x in RULE_IDS]
            continue

        if entity == "EMEA":
            meal01 = Check("MEAL-01", "superseded", detail="replaced by REG-03 for EMEA employees")
            reg02 = Check("REG-02", "not_applicable", detail="entity is EMEA, not APAC")
        else:
            group = days[day_key(r)]
            total = sum((per_person[g] for g in group), Fraction(0))
            homes = {g: HOME_CURRENCY.get(meals[g]["employee_country"]) for g in group}
            if entity == "APAC":
                cap, which = APAC_CAP, "APAC"
            elif None in homes.values():
                cap, which = None, ""
            elif any(currency(meals[g]) != homes[g] for g in group):
                cap, which = INTERNATIONAL_CAP, "international"
            else:
                cap, which = DOMESTIC_CAP, "domestic"
            shown = (f"{r['employee_id']} on {str(r.get('transaction_datetime'))[:10]}: "
                     f"{' + '.join(f'${per_person[g]:.2f} ({g})' for g in group)} = ${total:.2f} per person vs ${cap} ({which})")
            rule = "REG-02" if entity == "APAC" else "MEAL-01"
            if cap is None:
                cap_check = Check("ERR-MEAL-01", "fired", kind="signal",
                                  detail=f"MEAL-01: no home currency known for employee country {r['employee_country']!r}, "
                                         "so domestic or international cannot be told")
            elif total > Fraction(cap):
                cap_check = Check(rule, "fired", severity="medium", detail=shown)
            else:
                cap_check = Check(rule, "not_fired", detail=shown)
            if entity == "APAC":
                meal01, reg02 = Check("MEAL-01", "superseded", detail="replaced by REG-02 for APAC employees"), cap_check
            else:
                meal01, reg02 = cap_check, Check("REG-02", "not_applicable", detail=f"entity is {entity}, not APAC")

        receipt_total, n = money(r["total_amount_usd"], "total_amount_usd"), attendees(r)
        shown2 = f"receipt total ${receipt_total} vs ${MEAL02_THRESHOLD}, attendee_count={n}"
        if receipt_total > MEAL02_THRESHOLD and n is None:
            meal02 = Check("MEAL-02", "fired", severity="low", detail=shown2)
        else:
            meal02 = Check("MEAL-02", "not_fired", detail=shown2)
        out[rid] = [meal01, meal02, reg02]
    return out
