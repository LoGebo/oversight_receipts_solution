"""Load pipeline input. Refuses any record that still carries answer keys."""
import json
from pathlib import Path

INPUT = Path(__file__).resolve().parents[2] / "data_split" / "receipts_input.jsonl"
FORBIDDEN = {"labels", "notes"}


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
    receipts = [json.loads(line) for line in path.read_text().splitlines() if line]
    for r in receipts:
        _check(r, r.get("receipt_id", "?"))
    return receipts
