import importlib.util
import json
from pathlib import Path

from validator.loader import FORBIDDEN, load_receipts

_spec = importlib.util.spec_from_file_location("split_data", Path(__file__).resolve().parent.parent / "scripts" / "split_data.py")
split_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(split_data)

RECEIPT = {
    "receipt_id": "RCP-X",
    "mcc": "5812",
    "line_items": [
        {"line_id": "RCP-X-L1", "description_raw": "Draft IPA", "amount": 9.0, "labels": {"category": "alcohol", "restricted": True}},
        {"line_id": "RCP-X-L2", "description_raw": "Gratuity", "amount": 1.0, "notes": "x", "labels": {"category": "service_fee", "restricted": False}},
    ],
    "labels": {"disposition": "flag", "expected_exceptions": [], "review_signals": []},
    "notes": "why",
}


def test_split_input_carries_no_answers_and_keeps_everything_else(tmp_path):
    inp, _ = split_data.split(RECEIPT)
    p = tmp_path / "in.jsonl"
    p.write_text(json.dumps(inp) + "\n", encoding="utf-8")
    assert load_receipts(p) == [inp]            # the loader accepts it, so no answer key survived
    assert inp["mcc"] == "5812" and [li["description_raw"] for li in inp["line_items"]] == ["Draft IPA", "Gratuity"]
    assert not FORBIDDEN & inp.keys()


def test_split_gold_holds_every_answer():
    _, gold = split_data.split(RECEIPT)
    assert gold["labels"]["disposition"] == "flag"
    assert gold["notes"] == "why"
    assert gold["line_labels"]["RCP-X-L1"] == {"category": "alcohol", "restricted": True}
    assert set(gold["line_labels"]) == {"RCP-X-L1", "RCP-X-L2"}


def test_split_does_not_mutate_its_input():
    before = json.dumps(RECEIPT, sort_keys=True)
    split_data.split(RECEIPT)
    assert json.dumps(RECEIPT, sort_keys=True) == before
