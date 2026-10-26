import json
from pathlib import Path

import pytest

from validator.gold import OUT_OF_SCOPE, load_gold
from validator.loader import load_receipts

ROOT = Path(__file__).resolve().parent.parent
# Files allowed to mention the answer-key file.
ALLOWED = {"scripts/split_data.py", "src/validator/gold.py", "tests/test_no_leak.py"}


def test_input_has_no_answers():
    receipts = load_receipts()
    assert len(receipts) == 32
    assert sum(len(r["line_items"]) for r in receipts) == 79


def test_loader_rejects_labels():
    with pytest.raises(ValueError):
        # reuse the private check through a poisoned file
        p = ROOT / ".cache_poisoned.jsonl"
        p.write_text(json.dumps({"receipt_id": "X", "line_items": [{"labels": {}}]}) + "\n")
        try:
            load_receipts(p)
        finally:
            p.unlink()


def test_gold_is_complete_and_scope_counts():
    gold = load_gold()
    assert len(gold) == 32
    scored = [g for rid, g in gold.items() if rid not in OUT_OF_SCOPE]
    dispo = [g["labels"]["disposition"] for g in scored]
    assert (dispo.count("pass"), dispo.count("flag"), dispo.count("review")) == (9, 16, 3)
    assert sum(len(g["line_labels"]) for g in scored) == 65


def test_only_evaluation_code_touches_gold():
    offenders = []
    for path in list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py")) + list((ROOT / "tests").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel not in ALLOWED and "gold.jsonl" in path.read_text():
            offenders.append(rel)
    assert not offenders, offenders
