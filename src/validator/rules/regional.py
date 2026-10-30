"""Regional rules: REG-03 (EMEA meal cap), REG-04 (EMEA VAT receipt), REG-05 (conversion rate).

REG-01 lives in alcohol.py and REG-02 (APAC meal cap) in meals.py; for APAC employees REG-03/04 do
not apply. REG-03 replaces MEAL-01 for EMEA employees, and meals.py reports MEAL-01 as superseded
for them. REG-03 and REG-04 are whole-receipt rules and cite no lines (EXC-04).

The policy compares against euros converted "at the euro rate on the transaction date". For a EUR
receipt that is its own `fx_rate_to_usd`; for any other currency the data holds no euro rate, so the
caller passes `eur_usd`.
Limit: the record has no euro rate table. The engine's fallback (engine._eur_usd) is the one rate of the
batch's EUR receipts on that date; with none (or several), REG-03 and REG-04 refuse to guess and each
becomes its own ERR-REG-03 / ERR-REG-04 review signal, while every other rule still runs.
Limit: REG-03 compares each receipt's day total against that receipt's own euro rate, so on a day
whose receipts carry different rates the receipts can get different verdicts.
REG-05 says which rate to use and "raises nothing on its own; a missing rate is reported under DOC-04":
it is always not_fired here. Figures that do not match the recorded rate are the engine's ERR-input signal.
"""
from collections.abc import Sequence
from decimal import Decimal
from fractions import Fraction

from validator.check import Check
from validator.rules.common import currency, day_key, meal_per_person, money

REG03_CAP_EUR = Decimal("70")  # per person per day; strictly above fires
REG04_ABOVE_EUR = Decimal("50")  # receipt total; strictly above needs a VAT receipt
COUNTRIES = {"APAC": {"IN", "JP", "SG"}, "EMEA": {"GB", "DE", "FR", "NL", "IE", "PT", "ES"}}
RULE_IDS = ("REG-03", "REG-04", "REG-05")


def _entity(receipt: dict) -> str:
    """The entity, checked against employee_country: a mismatch would apply the wrong region's rules."""
    entity, country = receipt["entity"], receipt["employee_country"]
    expected = next((e for e, cs in COUNTRIES.items() if country in cs), "GLOBAL")
    if entity != expected:
        raise ValueError(f"entity {entity!r} does not match employee_country {country!r} (expected {expected})")
    return entity


def _eur_rate(receipt: dict, eur_usd: float | None) -> Decimal | None:
    """The euro rate on the transaction date, or None when there is none to use."""
    rate = receipt.get("fx_rate_to_usd") if currency(receipt) == "EUR" else None
    if rate is None:  # a EUR receipt missing its rate (DOC-04 reports that) can still use the caller's
        rate = eur_usd
    if rate is None:
        return None
    rate = money(rate, "EUR->USD rate")
    if rate <= 0:
        raise ValueError(f"EUR->USD rate must be positive, got {rate}")
    return rate


def _reg03(receipt: dict, categories: dict[str, str], same_day: list[dict], eur_usd: float | None) -> Check:
    mine = meal_per_person(receipt, categories)
    if mine is None:
        return Check("REG-03", "not_applicable", detail="not a meal receipt")
    day = day_key(receipt)
    total = mine
    for other in same_day:
        if day_key(other) != day or other["receipt_id"] == receipt["receipt_id"]:
            raise ValueError(f"{other['receipt_id']}: same_day must hold the employee's OTHER receipts of {day}")
        total += meal_per_person(other, categories) or 0
    rate = _eur_rate(receipt, eur_usd)
    if rate is None:
        return _no_rate("REG-03", receipt)
    cap = REG03_CAP_EUR * rate
    shown = f"{day[1]}: ${total:.2f} per person vs EUR {REG03_CAP_EUR} x {rate} = ${cap:.2f}"
    if total > Fraction(cap):
        return Check("REG-03", "fired", severity="medium", detail=shown)
    return Check("REG-03", "not_fired", detail=shown)


def _no_rate(rule: str, receipt: dict) -> Check:
    return Check(f"ERR-{rule}", "fired", kind="signal",
                 detail=f"{rule}: no EUR->USD rate on the transaction date for this {receipt['currency']} receipt")


def _reg04(receipt: dict, eur_usd: float | None) -> Check:
    if currency(receipt) == "EUR":
        eur = money(receipt["total_amount"], "total_amount")
    else:
        rate = _eur_rate(receipt, eur_usd)
        if rate is None:
            return _no_rate("REG-04", receipt)
        eur = money(receipt["total_amount_usd"], "total_amount_usd") / rate
    shown = f"total EUR {eur:.2f} vs EUR {REG04_ABOVE_EUR}"
    if eur <= REG04_ABOVE_EUR:
        return Check("REG-04", "not_fired", detail=shown)
    # The expense record has no VAT-number field, so per REG-04 the number is always missing.
    return Check("REG-04", "fired", severity="low", detail=f"{shown}; no merchant VAT number recorded")


REG05 = Check("REG-05", "not_fired", detail="says which rate to use and raises nothing on its own; a missing rate is DOC-04")


def regional_checks(receipt: dict, categories: dict[str, str], same_day: Sequence[dict] = (),
                    eur_usd: float | None = None) -> list[Check]:
    """One Check for each of REG-03, REG-04, REG-05 (in that order).

    `categories` maps line_id -> category for this receipt AND every receipt in `same_day`: the same
    employee's other receipts on the same calendar date (REG-03 adds them up per day, as MEAL-01 does).
    `eur_usd`: the euro rate on the transaction date, needed only for a non-EUR EMEA receipt.
    """
    entity = _entity(receipt)
    if entity != "EMEA":
        why = f"entity is {entity}, not EMEA" + (" (APAC meal cap is REG-02)" if entity == "APAC" else "")
        return [Check("REG-03", "not_applicable", detail=why), Check("REG-04", "not_applicable", detail=why), REG05]
    return [_reg03(receipt, categories, list(same_day), eur_usd), _reg04(receipt, eur_usd), REG05]
