"""Documentation rules: DOC-01 (itemization), DOC-02 (legibility), DOC-03 (type vs contents), DOC-04 (FX).

All four are rules about the receipt as a whole, so they cite no lines (EXC-04), all medium.
A non-itemized receipt's charge is `other` by definition (EXC-03, taxonomy), whatever the classifier
said, so DOC-03 never applies to it. Thresholds use the USD total (DOC-04).
"""
from datetime import datetime
from decimal import Decimal

from validator.check import Check
from validator.rules.common import FOOD_OR_DRINK, MEAL_TYPES, currency, itemized, money

ITEMIZE_ABOVE = Decimal("75")  # USD; strictly above must be itemized
COVERS = {
    **{t: set(FOOD_OR_DRINK) for t in MEAL_TYPES},
    "Client Gifts": {"gift", "gift_card", "jewelry"},
    "Lodging": {"lodging", "ground_transport", "laundry_service"},
    "Travel - Other": {"laundry_service", "health_otc", "ground_transport", "clothing", "personal_care"},
    "Office Supplies": {"office_supplies", "computer_accessory"},
    "Computer Equipment": {"computer_accessory", "personal_electronics", "software_subscription"},
    "Software": {"software_subscription"},
}
TAXONOMY = {
    "alcohol", "tobacco", "personal_electronics", "gift", "gift_card", "household_goods", "personal_care",
    "clothing", "gambling", "jewelry", "food_beverage", "computer_accessory", "office_supplies", "lodging",
    "ground_transport", "airfare", "laundry_service", "health_otc", "software_subscription", "service_fee", "other",
}
EXTENSIONS = {"mobile_handset": "other", "entertainment_venue": "other",  # engine refinements of `other` -> taxonomy
              "prescription_medication": "other"}
IGNORED = {"service_fee", "other"}  # DOC-03: fees, gratuities and `other` do not count
RULE_IDS = ("DOC-01", "DOC-02", "DOC-03", "DOC-04")


def taxonomy_categories(receipt: dict, categories: dict[str, str]) -> dict[str, str]:
    """line_id -> taxonomy category. Missing line -> KeyError; unknown category -> ValueError."""
    whole = not itemized(receipt)
    out = {}
    for li in receipt["line_items"]:
        c = categories[li["line_id"]]
        if c not in TAXONOMY and c not in EXTENSIONS:
            raise ValueError(f"{li['line_id']}: unknown category {c!r}")
        out[li["line_id"]] = "other" if whole else EXTENSIONS.get(c, c)
    return out


def _blank(value, what: str) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        raise ValueError(f"{what} must be a string, got {value!r}")
    return not value.strip()


def _doc02(receipt: dict) -> Check:
    missing = []
    if _blank(receipt.get("merchant_name"), "merchant_name"):
        missing.append("merchant name")
    when = receipt.get("transaction_datetime")
    if _blank(when, "transaction_datetime"):
        missing.append("transaction date")
    else:
        datetime.fromisoformat(when)  # an unparseable date is bad data (ValueError), not "illegible"
    if receipt.get("total_amount") is None:
        missing.append("total")
    else:
        money(receipt["total_amount"], "total_amount")
    if missing:
        return Check("DOC-02", "fired", severity="medium", detail=f"missing {', '.join(missing)}")
    return Check("DOC-02", "not_fired", detail="merchant name, date and total are recorded")


def _doc03(receipt: dict, cat: dict[str, str]) -> Check:
    kind = receipt["submitted_expense_type"]
    counted = sorted({c for c in cat.values() if c not in IGNORED})
    if not counted:
        return Check("DOC-03", "not_applicable", detail="no line left after fees, gratuities and `other`")
    if kind not in COVERS:  # the table says what each declaration covers; for any other, DOC-03 cannot be decided
        return Check("ERR-DOC-03", "fired", kind="signal",
                     detail=f"DOC-03: expense type {kind!r} is not in the policy table, so its contents cannot be checked")
    shown = f"{kind!r} covers {sorted(COVERS[kind])}; lines are {counted}"
    if COVERS[kind].isdisjoint(counted):
        return Check("DOC-03", "fired", severity="medium", detail=shown)
    return Check("DOC-03", "not_fired", detail=shown)


def _doc04(receipt: dict) -> Check:
    cur = receipt.get("currency")
    if _blank(cur, "currency"):
        # ambiguity: with no currency recorded the receipt cannot show it is in USD; the literal reading
        # is that it failed to "record the transaction currency", so DOC-04 fires.
        return Check("DOC-04", "fired", severity="medium", detail="no transaction currency recorded")
    cur = currency(receipt)
    if cur == "USD":
        return Check("DOC-04", "not_applicable", detail="receipt is in USD")
    rate = receipt.get("fx_rate_to_usd")
    if rate is None:
        return Check("DOC-04", "fired", severity="medium", detail=f"{cur} receipt without a conversion rate")
    if money(rate, "fx_rate_to_usd") <= 0:
        raise ValueError(f"fx_rate_to_usd must be positive, got {rate!r}")
    return Check("DOC-04", "not_fired", detail=f"{cur} at rate {rate}")


def _doc01(receipt: dict, reported: bool) -> Check:
    usd = receipt.get("total_amount_usd")
    if usd is None:
        if not reported:  # a USD total that is simply absent, with nothing else firing, is a data bug
            raise ValueError("total_amount_usd is missing")
        return Check("DOC-01", "not_applicable", detail="no USD total; reported under DOC-02/DOC-04")
    usd = money(usd, "total_amount_usd")
    shown = f"${usd} vs ${ITEMIZE_ABOVE}, itemized={receipt['itemized']}"
    if not receipt["itemized"] and usd > ITEMIZE_ABOVE:
        return Check("DOC-01", "fired", severity="medium", detail=shown)
    return Check("DOC-01", "not_fired", detail=shown)


def documentation_checks(receipt: dict, categories: dict[str, str]) -> list[Check]:
    """One Check for each of DOC-01..DOC-04 (in that order). `categories` maps line_id -> category."""
    cat = taxonomy_categories(receipt, categories)
    doc02, doc04 = _doc02(receipt), _doc04(receipt)
    reported = doc02.status == "fired" or doc04.status == "fired"
    return [_doc01(receipt, reported), doc02, _doc03(receipt, cat), doc04]
