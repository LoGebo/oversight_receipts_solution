"""Item rules decided by line category: TECH-01..04, ENT-01, ENT-02, PERS-03, HOUSE-01, LAUNDRY-01.

Each rule fires at most once per receipt and cites every line that breaks it (EXC-04).
`mobile_handset` and `entertainment_venue` are engine-internal refinements of `other`: the taxonomy files
phones and event tickets under `other`, and the classifier composes these from the model's `other` +
`other_kind`, so TECH-03 and ENT-01 can act on them. Reported as `other`. (`prescription_medication`, the third,
is HEALTH-01's: rules/health.py.)
EXC-02: a reference waives a rule only if it is the kind that rule asks for. Every ref in the data
starts with "PA-" (a pre-approval), so today only TECH-02 can be waived.
Limit: ENT-01 is triggered by the line category only (entertainment_venue), never by the merchant's MCC: its
text names the spend ("golf, sporting events, theatre, concerts, and similar venue spend") and no merchant
code, and merchant-category-risk.md says an MCC describes "where the money was spent, not what was bought".
LAUNDRY-01 "trip record", read as HEALTH-01 reads it: the receipt is linked to a trip (`trip_id`)
and records its length (`trip_nights`). Missing either is "no trip record", a low exception.
"""
from decimal import Decimal

from validator.check import Check
from validator.rules.common import money

TECH02_CAP = Decimal("200")  # per item, USD unit price; strictly above fires
LAUNDRY_MIN_NIGHTS = 4
RULE_IDS = ("TECH-01", "TECH-02", "TECH-03", "TECH-04", "ENT-01", "ENT-02", "PERS-03", "HOUSE-01", "LAUNDRY-01")


def ref_kind(ref) -> str | None:
    """The kind of approval a pre_approval_ref is. Only pre-approvals ("PA-...") are recognised."""
    return "pre_approval" if isinstance(ref, str) and ref.startswith("PA-") else None


def _simple(rule: str, ids: tuple, severity: str, what: str, needs: str | None = None, have: str | None = None) -> Check:
    if not ids:
        return Check(rule, "not_applicable", detail=f"no {what} line")
    if needs is not None and have == needs:
        return Check(rule, "not_fired", detail=f"{what}: {needs} reference satisfies {rule}")
    detail = f"categorised {what}" if needs is None else f"{what} without a {needs} reference (ref kind: {have})"
    return Check(rule, "fired", severity=severity, line_ids=ids, detail=detail)


def _tech02(lines: list[dict], have: str | None) -> Check:
    if not lines:
        return Check("TECH-02", "not_applicable", detail="no computer_accessory line")
    over, shown = [], []
    for li in lines:
        q = li["quantity"]
        if type(q) not in (int, float) or not float(q).is_integer() or q < 1:  # 1.0 is a count of one; bools and 1.5 are not counts
            raise ValueError(f"{li['line_id']}: quantity must be a positive int, got {q!r}")
        unit = money(li["amount_usd"], li["line_id"]) / int(q)
        shown.append(f"{li['line_id']} ${unit:.2f}")
        if unit > TECH02_CAP:
            over.append(li["line_id"])
    detail = f"unit prices {', '.join(shown)} vs ${TECH02_CAP} per item"
    if not over:
        return Check("TECH-02", "not_fired", detail=detail)
    if have == "pre_approval":
        return Check("TECH-02", "not_fired", detail=f"{detail}; pre-approval reference satisfies TECH-02")
    return Check("TECH-02", "fired", severity="medium", line_ids=tuple(over), detail=f"{detail}; no pre-approval reference")


def _laundry(ids: tuple, receipt: dict) -> Check:
    if not ids:
        return Check("LAUNDRY-01", "not_applicable", detail="no laundry_service line")
    nights = receipt.get("trip_nights")
    if receipt.get("trip_id") is None or nights is None:
        return Check("LAUNDRY-01", "fired", severity="low", line_ids=ids, detail="no trip record")
    if type(nights) is not int:
        raise ValueError(f"trip_nights must be an int or None, got {nights!r}")
    shown = f"trip of {nights} nights vs {LAUNDRY_MIN_NIGHTS}+ required"
    if nights >= LAUNDRY_MIN_NIGHTS:
        return Check("LAUNDRY-01", "not_fired", detail=shown)
    return Check("LAUNDRY-01", "fired", severity="low", line_ids=ids, detail=shown)


def line_checks(receipt: dict, categories: dict[str, str]) -> list[Check]:
    """One Check for each of RULE_IDS (in that order). `categories` maps line_id -> category."""
    items = receipt["line_items"]
    cat = {li["line_id"]: categories[li["line_id"]] for li in items}  # a missing line raises KeyError

    def lines_of(category: str) -> tuple:
        return tuple(i for i, c in cat.items() if c == category)

    have = ref_kind(receipt.get("pre_approval_ref"))
    return [
        _simple("TECH-01", lines_of("personal_electronics"), "high", "personal_electronics"),
        _tech02([li for li in items if cat[li["line_id"]] == "computer_accessory"], have),
        _simple("TECH-03", lines_of("mobile_handset"), "high", "mobile_handset"),
        _simple("TECH-04", lines_of("software_subscription"), "low", "software_subscription", "manager_approval", have),
        _simple("ENT-01", lines_of("entertainment_venue"), "medium", "entertainment_venue", "vp_approval", have),
        _simple("ENT-02", lines_of("gambling"), "high", "gambling"),
        _simple("PERS-03", lines_of("tobacco"), "high", "tobacco"),
        _simple("HOUSE-01", lines_of("household_goods"), "medium", "household_goods"),
        _laundry(lines_of("laundry_service"), receipt),
    ]
