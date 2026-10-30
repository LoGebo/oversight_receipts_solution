"""Personal items: PERS-01 (personal_care) and PERS-02 (clothing), both medium.

Baggage-delay carve-out: with a baggage-delay reference (EXC-02), ONE $150 allowance per delay is
shared between toiletries and clothing, so the two categories are summed together. At or under $150
both pass; above it, each rule that has lines fires, citing every line involved in the allowance
(both categories). A pre-approval ("PA-...") is not a baggage-delay reference and waives nothing.
`ref_kind` recognises no baggage-delay reference today, so in the data the carve-out never applies.
"""
from decimal import Decimal

from validator.check import Check
from validator.rules.common import money
from validator.rules.lines import ref_kind

ALLOWANCE = Decimal("150")  # USD per delay, shared by both categories; strictly above fires
RULES = (("PERS-01", "personal_care"), ("PERS-02", "clothing"))
RULE_IDS = tuple(r for r, _ in RULES)


def personal_checks(receipt: dict, categories: dict[str, str]) -> list[Check]:
    """One Check for each of PERS-01, PERS-02 (in that order). `categories` maps line_id -> category."""
    items = receipt["line_items"]
    cat = {li["line_id"]: categories[li["line_id"]] for li in items}  # a missing line raises KeyError
    own = {c: tuple(i for i, k in cat.items() if k == c) for _, c in RULES}
    involved = tuple(i for i, k in cat.items() if k in own)
    have = ref_kind(receipt.get("pre_approval_ref"))

    shown, over = "", False
    if have == "baggage_delay":
        total = sum((money(li["amount_usd"], li["line_id"]) for li in items if li["line_id"] in involved), Decimal(0))
        shown = f"personal_care + clothing ${total} vs ${ALLOWANCE} shared baggage-delay allowance"
        over = total > ALLOWANCE
    out = []
    for rule, c in RULES:
        if not own[c]:
            out.append(Check(rule, "not_applicable", detail=f"no {c} line"))
        elif have != "baggage_delay":
            out.append(Check(rule, "fired", severity="medium", line_ids=own[c],
                             detail=f"{c} without a baggage_delay reference (ref kind: {have})"))
        elif over:
            out.append(Check(rule, "fired", severity="medium", line_ids=involved, detail=shown))
        else:
            out.append(Check(rule, "not_fired", detail=shown))
    return out
