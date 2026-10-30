"""engine_api: how to CALL the deterministic engine from any notebook.

The real engine lives in `validator/` (read-only copy in `engine/validator`, standard library only).
This module holds two thin wrappers and NO rule logic of its own:

    evaluate_receipts(receipts, categories, gift_for=None, uncertain=None) -> {receipt_id: Result}
    evaluate_history(history)                                              -> {receipt_id: Result}   (red-team history format)

`Result.disposition` is "pass" | "review" | "flag"; `Result.fired` lists (rule, severity, detail).
"""
from __future__ import annotations
import sys, copy, collections
from dataclasses import dataclass
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent / "engine"
if str(ENGINE_DIR) not in sys.path: sys.path.insert(0, str(ENGINE_DIR))
from validator.engine import run_engine, EXPECTED, FAMILIES      # noqa: E402  (the real engine)
from validator.normaliser import normalise_receipt               # noqa: E402


@dataclass
class Result:
    receipt_id: str
    disposition: str
    fired: list            # [(rule_id, severity or 'signal', detail)]
    considered: list       # rules the retriever proposed
    superseded: list


def _wrap(res):
    out = {}
    for rid, x in res.items():
        fired = [(c.rule_id, c.severity or ("signal" if c.kind == "signal" else "-"), c.detail) for c in x.checks if c.status == "fired"]
        sup = [c.rule_id for c in x.checks if c.status == "superseded"]
        out[rid] = Result(rid, str(x.disposition), fired, sorted(x.considered), sup)
    return out


def evaluate_receipts(receipts, categories, gift_for=None, uncertain=None):
    """receipts: list of dicts like receipts_input.jsonl; categories: {line_id: category}; gift_for: {line_id: (kind, name)}."""
    recs = [normalise_receipt(copy.deepcopy(r)) for r in receipts]
    return _wrap(run_engine(recs, dict(categories), dict(gift_for) if gift_for else None, uncertain))


def evaluate_history(h):
    """h: red-team history: each line carries `category` (or the history carries `_cats` and `_gift_for`). Does not modify h."""
    h = copy.deepcopy(h); cats, gf, recs = dict(h.get("_cats") or {}), {k: (v[0], v[1]) for k, v in (h.get("_gift_for") or {}).items()}, []
    for r in h["receipts"]:
        r.pop("planted", None)
        for k, v in (r.pop("gift_for", None) or {}).items(): gf[k] = (v[0], v[1])
        for li in r["line_items"]:
            if "category" in li: cats[li["line_id"]] = li.pop("category")
        recs.append(normalise_receipt(r))
    return _wrap(run_engine(recs, cats, gf or None, None))


def summary(res):
    return dict(collections.Counter(x.disposition for x in res.values()))


def create_receipt(id, expense_type, merchant, mcc, when, lines, *, entity="GLOBAL", attendees=None, trip=None, nights=None, pre_approval=None, itemized=True, currency="USD"):
    """Build a minimal valid receipt. lines: [(description, category, amount, quantity)] -> (receipt, {line_id: category}). Demos only."""
    items, cats = [], {}
    for i, (desc, cat, amount, qty) in enumerate(lines, 1):
        lid = f"{id}-L{i}"; cats[lid] = cat
        items.append({"line_id": lid, "description_raw": desc, "language": "en", "quantity": qty, "unit_price": round(amount / qty, 2), "amount": amount, "amount_usd": amount})
    total = round(sum(l["amount"] for l in items), 2)
    r = {"receipt_id": id, "employee_id": "E-9000", "employee_country": "US", "entity": entity, "submitted_expense_type": expense_type, "merchant_name": merchant, "mcc": mcc, "mcc_description": "demo",
         "transaction_datetime": when, "currency": currency, "fx_rate_to_usd": 1.0, "total_amount": total, "total_amount_usd": total, "attendee_count": attendees, "trip_id": trip, "trip_nights": nights,
         "pre_approval_ref": pre_approval, "itemized": itemized, "line_items": items}
    return r, cats


def probe(cases):
    """cases: list of (label, receipt, categories, gift_for). Returns rows (label, disposition, fired rules)."""
    rows = []
    for label, r, cats, gf in cases:
        x = evaluate_receipts([r], cats, gf)[r["receipt_id"]]
        rows.append((label.replace("$", "&#36;"), x.disposition, ", ".join(f"{a}({b})" for a, b, _ in x.fired) or "-"))
    return rows
