"""HEALTH-01, medication: over-the-counter (category health_otc) and prescription (prescription_medication).
The one cross-receipt rule here.

OTC medication is reimbursable only on a receipt linked to a trip (`trip_id`), up to $25 in total
across all of that trip's receipts (USD, strictly above fires). Above it, or on a receipt with no
trip, it is a low exception on each such receipt, citing that receipt's own medication lines.
Prescription medication "is never reimbursable on an expense report and is a medium exception": any
amount, trip or not. The taxonomy files it under `other`; the classifier composes this engine category
from `other` + other_kind, as for TECH-03 and ENT-01, and it never counts toward the OTC cap.
Reading (one Check per rule id): with both branches on one receipt, the severity is the higher (medium)
and the cited lines are the union; OTC lines within the cap are reimbursable, so they are not cited.
"""
from collections import defaultdict
from decimal import Decimal

from validator.check import Check
from validator.rules.common import money

CAP = Decimal("25")  # USD per trip, across all its receipts
RULE_IDS = ("HEALTH-01",)


def _otc(trip, ids: tuple[str, ...], spent: Decimal | None) -> Check:
    if not ids:
        return Check("HEALTH-01", "not_applicable", detail="no health_otc line")
    if trip is None:
        return Check("HEALTH-01", "fired", severity="low", line_ids=ids, detail="no trip record")
    shown = f"OTC medication on {trip}: ${spent} across its receipts vs ${CAP}"
    if spent > CAP:
        return Check("HEALTH-01", "fired", severity="low", line_ids=ids, detail=shown)
    return Check("HEALTH-01", "not_fired", detail=shown)


def health_checks(receipts: list[dict], categories: dict[str, str]) -> dict[str, Check]:
    """receipt_id -> HEALTH-01 Check, for every receipt. `categories` maps line_id -> category
    over ALL receipts (line ids are globally unique); a missing line raises KeyError."""
    meds = {r["receipt_id"]: [li for li in r["line_items"] if categories[li["line_id"]] == "health_otc"]
            for r in receipts}
    per_trip = defaultdict(Decimal)
    for r in receipts:
        if r.get("trip_id") is not None:
            per_trip[r["trip_id"]] += sum((money(li["amount_usd"], li["line_id"]) for li in meds[r["receipt_id"]]), Decimal(0))

    out = {}
    for r in receipts:
        rid, trip = r["receipt_id"], r.get("trip_id")
        otc = _otc(trip, tuple(li["line_id"] for li in meds[rid]), per_trip.get(trip))
        rx = {li["line_id"] for li in r["line_items"] if categories[li["line_id"]] == "prescription_medication"}
        if not rx:
            out[rid] = otc
            continue
        cited = rx | set(otc.line_ids if otc.status == "fired" else ())
        detail = "prescription medication is never reimbursable" + (f"; {otc.detail}" if otc.status == "fired" else "")
        out[rid] = Check("HEALTH-01", "fired", severity="medium",
                         line_ids=tuple(li["line_id"] for li in r["line_items"] if li["line_id"] in cited), detail=detail)
    return out
