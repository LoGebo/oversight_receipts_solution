"""Load pipeline input. Refuses any record that still carries answer keys, and any batch the engine would
misread: a record without `receipt_id` or a `line_items` list, or a receipt_id or line_id used twice (categories
are keyed by line_id across the batch, so a repeated one would silently read another receipt's line)."""
import json
from collections import Counter
from pathlib import Path

INPUT = Path(__file__).resolve().parents[2] / "data_split" / "receipts_input.jsonl"
FORBIDDEN = {"labels", "notes", "line_labels"}  # "line_labels" is how gold.jsonl names the per-line answers


def _check(obj, where: str) -> None:
    if isinstance(obj, dict):
        bad = FORBIDDEN & obj.keys()
        if bad:
            raise ValueError(f"answer key {sorted(bad)} found in input at {where}")
        for k, v in obj.items():
            _check(v, f"{where}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _check(v, f"{where}[{i}]")


def load_receipts(path: Path = INPUT) -> list[dict]:
    receipts = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in receipts:
        _check(r, r.get("receipt_id", "?"))
    for i, r in enumerate(receipts, 1):
        if not isinstance(r.get("receipt_id"), str) or not isinstance(r.get("line_items"), list):
            raise ValueError(f"{path.name} record {i}: needs a receipt_id string and a line_items list")
        if not all(isinstance(li, dict) and "line_id" in li for li in r["line_items"]):
            raise ValueError(f"{r['receipt_id']}: every line item needs a line_id")
    for what, ids in (("receipt_id", [r["receipt_id"] for r in receipts]),
                      ("line_id", [li["line_id"] for r in receipts for li in r["line_items"]])):
        dup = sorted(k for k, n in Counter(ids).items() if n > 1)
        if dup:
            raise ValueError(f"{path.name}: duplicate {what} {dup}")
    return receipts
