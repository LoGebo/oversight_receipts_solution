"""Answer key. Evaluation only: nothing in the pipeline may import this module."""
import json
from pathlib import Path

GOLD = Path(__file__).resolve().parents[2] / "data_split" / "gold.jsonl"

# Out of scope per the brief (timing rules TIME-01..04 are optional): not scored.
OUT_OF_SCOPE = {"RCP-020", "RCP-021", "RCP-029", "RCP-030"}


def load_gold() -> dict[str, dict]:
    rows = [json.loads(line) for line in GOLD.read_text().splitlines() if line]
    return {r["receipt_id"]: r for r in rows}
