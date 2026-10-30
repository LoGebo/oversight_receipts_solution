"""Alcohol rules: ALC-01, ALC-02, ALC-03 (global) and REG-01 (APAC override).

The four are decided together because only one branch can apply to a receipt:
  APAC employee               -> REG-01 fires; ALC-01/02/03 are superseded
  not a restaurant/bar/hotel  -> ALC-03 fires alone (retail alcohol is never reimbursable)
  on premises                 -> ALC-01 needs Client Entertainment with 2+ attendees;
                                 if it passes, ALC-02 caps alcohol at $30 per attendee
  no MCC recorded             -> on premises or retail cannot be told: ALC-01/02/03 are not_applicable and
                                 the engine's ERR-input signal sends the receipt to review
"""
from decimal import Decimal

from validator.check import Check
from validator.rules.common import attendees, mcc_code, money

ON_PREMISES_MCC = {"5812", "5813", "7011"}  # restaurant, bar (MCC-03: a bar is on premises), hotel
CAP_PER_ATTENDEE = Decimal("30")
RULE_IDS = ("ALC-01", "ALC-02", "ALC-03", "REG-01")


def alcohol_checks(receipt: dict, categories: dict[str, str]) -> list[Check]:
    """One Check for each of ALC-01, ALC-02, ALC-03, REG-01 (in that order).

    `categories` maps line_id -> category, from the classifier (or hand-written in tests).
    """
    lines = [li for li in receipt["line_items"] if categories[li["line_id"]] == "alcohol"]
    ids = tuple(li["line_id"] for li in lines)
    mcc, entity = mcc_code(receipt), receipt["entity"]  # " 5921" or 5921 must not slip past the MCC sets

    if not lines:
        return [Check(r, "not_applicable", detail="no alcohol line") for r in RULE_IDS]

    if entity == "APAC":
        replaced = "replaced by REG-01 for APAC employees"
        return [
            Check("ALC-01", "superseded", detail=replaced),
            Check("ALC-02", "superseded", detail=replaced),
            Check("ALC-03", "superseded", detail=replaced),
            Check("REG-01", "fired", severity="high", line_ids=ids, detail="APAC employee: alcohol is never reimbursable"),
        ]

    not_apac = Check("REG-01", "not_applicable", detail=f"entity is {entity}, not APAC")

    if mcc is None:
        unknown = "no MCC recorded: on premises or retail cannot be told (ERR-input)"
        return [Check(r, "not_applicable", detail=unknown) for r in ("ALC-01", "ALC-02", "ALC-03")] + [not_apac]

    if mcc not in ON_PREMISES_MCC:
        retail = "retail merchant: ALC-03 alone applies"
        return [
            Check("ALC-01", "not_applicable", detail=retail),
            Check("ALC-02", "not_applicable", detail=retail),
            Check("ALC-03", "fired", severity="high", line_ids=ids, detail=f"MCC {mcc} is not a restaurant, bar or hotel"),
            not_apac,
        ]

    alc03 = Check("ALC-03", "not_applicable", detail=f"MCC {mcc} is on premises")
    kind, n = receipt["submitted_expense_type"], attendees(receipt)
    permitted = kind == "Client Entertainment" and n is not None and n >= 2

    if not permitted:
        alc01 = Check("ALC-01", "fired", severity="high", line_ids=ids,
                      detail=f"type={kind!r}, attendees={n}: needs Client Entertainment with 2+ attendees")
        alc02 = Check("ALC-02", "not_applicable", detail="alcohol is not permitted under ALC-01")
        return [alc01, alc02, alc03, not_apac]

    alc01 = Check("ALC-01", "not_fired", detail=f"Client Entertainment with {n} attendees")
    total = sum((money(li["amount_usd"], li["line_id"]) for li in lines), Decimal(0))
    shown = f"${total} / {n} = ${total / n:.2f} per attendee vs ${CAP_PER_ATTENDEE}"
    if total > CAP_PER_ATTENDEE * n:  # strict: exactly $30 per attendee passes
        alc02 = Check("ALC-02", "fired", severity="medium", line_ids=ids, detail=shown)
    else:
        alc02 = Check("ALC-02", "not_fired", detail=shown)
    return [alc01, alc02, alc03, not_apac]
