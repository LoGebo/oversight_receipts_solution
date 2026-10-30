"""Answer key. Evaluation only: nothing in the pipeline may import this module."""
import json
from pathlib import Path

GOLD = Path(__file__).resolve().parents[2] / "data_eval" / "gold.jsonl"

# Out of scope per the brief (timing rules TIME-01..04 are optional): not scored.
OUT_OF_SCOPE = {"RCP-020", "RCP-021", "RCP-029", "RCP-030"}


def load_gold() -> dict[str, dict]:
    rows = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = {r["receipt_id"]: r for r in rows}
    if len(out) != len(rows):
        raise ValueError("duplicate receipt_id in gold.jsonl")
    return out
