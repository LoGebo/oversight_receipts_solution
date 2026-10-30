import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from validator.gold import OUT_OF_SCOPE, load_gold
from validator.loader import load_receipts

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "validator"
# Only the answer-key module (and, later, an evaluation package) may touch the answers.
EVAL_ONLY = ("gold.py", "evaluation")
LEAK_STRING = re.compile(r"gold|receipts\.jsonl|data_eval|data_heldout")  # answer files, or the original that holds them


def _pipeline_modules():
    return [p for p in SRC.rglob("*.py") if not any(part in EVAL_ONLY for part in p.relative_to(SRC).parts)]


def test_input_file_loads_and_has_the_expected_size():
    receipts = load_receipts()
    assert len(receipts) == 32
    assert sum(len(r["line_items"]) for r in receipts) == 79


@pytest.mark.parametrize("key", ["labels", "notes", "line_labels"])
@pytest.mark.parametrize("nested", [False, True])
def test_loader_rejects_answer_keys_at_any_depth(tmp_path, key, nested):
    record = {"receipt_id": "X", "line_items": [{key: {}}]} if nested else {"receipt_id": "X", key: {}}
    p = tmp_path / "poisoned.jsonl"
    p.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="answer key"):
        load_receipts(p)


@pytest.mark.parametrize("records, match", [
    ([{"line_items": []}], "needs a receipt_id string and a line_items list"),
    ([{"receipt_id": "X"}], "needs a receipt_id string and a line_items list"),
    ([{"receipt_id": "X", "line_items": {"line_id": "X-L1"}}], "needs a receipt_id string and a line_items list"),
    ([{"receipt_id": "X", "line_items": [{"description_raw": "a"}]}], "every line item needs a line_id"),
    ([{"receipt_id": "X", "line_items": []}, {"receipt_id": "X", "line_items": []}], r"duplicate receipt_id \['X'\]"),
    ([{"receipt_id": "X", "line_items": [{"line_id": "L"}]}, {"receipt_id": "Y", "line_items": [{"line_id": "L"}]}],
     r"duplicate line_id \['L'\]"),
])
def test_loader_rejects_records_the_engine_would_misread(tmp_path, records, match):
    p = tmp_path / "bad.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        load_receipts(p)


def test_gold_is_complete_and_scope_counts():
    gold = load_gold()
    assert len(gold) == 32
    scored = [g for rid, g in gold.items() if rid not in OUT_OF_SCOPE]
    dispo = [g["labels"]["disposition"] for g in scored]
    assert (dispo.count("pass"), dispo.count("flag"), dispo.count("review")) == (9, 16, 3)
    assert sum(len(g["line_labels"]) for g in scored) == 65


def test_answer_file_is_outside_the_input_directory():
    assert sorted(p.name for p in (ROOT / "data_split").iterdir()) == ["receipts_input.jsonl"]
    assert (ROOT / "data_eval" / "gold.jsonl").exists()


def test_pipeline_code_never_imports_the_answer_key_or_evaluation():
    offenders = []
    for path in _pipeline_modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names]
            if any(n == "validator.gold" or n.endswith(".gold") or n == "gold" or n == "validator.evaluation"
                   or n.startswith("validator.evaluation.") or n == "evaluation" for n in names):
                offenders.append(f"{path.name}: imports {names}")
    assert not offenders, offenders


def _text(node):
    """The str a constant expression spells: literals (bytes too), `+` of them, and chr(<int>); else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
        return node.value if isinstance(node.value, str) else node.value.decode("latin-1")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "chr" and len(node.args) == 1 \
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, int):
        return chr(node.args[0].value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _text(node.left), _text(node.right)
        return None if left is None or right is None else left + right
    return None


def test_pipeline_code_never_names_the_answer_files():
    offenders = []
    for path in _pipeline_modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            text = _text(node)
            if text is not None and LEAK_STRING.search(text):
                offenders.append(f"{path.name}: {text!r}")
    assert not offenders, offenders


BANNED_MODULES = ("importlib", "subprocess", "glob")  # dynamic imports, other processes, directory listing
BANNED_CALLS = ("__import__", "listdir", "scandir")


def test_pipeline_code_has_no_way_around_the_import_and_name_checks():
    offenders = []
    for path in _pipeline_modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            elif isinstance(node, (ast.Name, ast.Attribute)):
                names = [getattr(node, "id", None) or node.attr]
                offenders += [f"{path.name}: {n}" for n in names if n in BANNED_CALLS]
                continue
            else:
                continue
            offenders += [f"{path.name}: imports {n}" for n in names if n.split(".")[0] in BANNED_MODULES]
    assert not offenders, offenders


AUDIT = """
import json, re, sys
seen, spawned = [], []
WATCH = ("open", "os.listdir", "os.scandir", "subprocess.Popen")
sys.addaudithook(lambda event, args: (spawned if event == "subprocess.Popen" else seen).append(repr(args))
                 if event in WATCH else None)
from validator import run
code = run.main(sys.argv[1:])
leak = re.compile(r"gold|/receipts\\.jsonl|data_heldout|data_eval")
print(json.dumps({"code": code, "leaks": sorted({p for p in seen if leak.search(p)}), "spawned": spawned,
                  "modules": sorted(m for m in sys.modules if m == "validator.gold" or m.startswith("validator.evaluation"))}))
"""


def test_a_real_run_never_opens_the_answers(tmp_path):
    # no key of either provider, and a copy of the warm cache: no paid call, nothing written into the repo cache
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")}
    shutil.copytree(ROOT / ".cache" / "classifier", tmp_path / "cache")
    out = subprocess.run([sys.executable, "-c", AUDIT, "--out", str(tmp_path / "out"), "--cache", str(tmp_path / "cache")],
                         cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout.splitlines()[-1])
    assert got == {"code": 0, "leaks": [], "spawned": [], "modules": []}
    assert (tmp_path / "out" / "report.jsonl").exists()
