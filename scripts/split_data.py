"""Split data/receipts.jsonl into pipeline input (no answers) and gold (answers only).

The pipeline may only read data_split/receipts_input.jsonl.
Only src/validator/gold.py (evaluation) may read data_split/gold.jsonl.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "receipts.jsonl"
OUT = ROOT / "data_split"


def split(receipt: dict) -> tuple[dict, dict]:
    inp = {k: v for k, v in receipt.items() if k not in ("labels", "notes")}
    inp["line_items"] = [{k: v for k, v in li.items() if k != "labels"} for li in receipt["line_items"]]
    gold = {
        "receipt_id": receipt["receipt_id"],
        "labels": receipt["labels"],
        "notes": receipt["notes"],
        "line_labels": {li["line_id"]: li["labels"] for li in receipt["line_items"]},
    }
    return inp, gold


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with SRC.open() as f, (OUT / "receipts_input.jsonl").open("w") as fi, (OUT / "gold.jsonl").open("w") as fg:
        for line in f:
            inp, gold = split(json.loads(line))
            fi.write(json.dumps(inp, ensure_ascii=False) + "\n")
            fg.write(json.dumps(gold, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
