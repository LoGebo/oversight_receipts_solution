"""Smoke tests for the Streamlit viewer (viewer/app.py). Run: uv run --group dev --group viewer pytest tests/test_viewer.py"""

import ast
import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "viewer" / "app.py"
BANNER = "The answer key is shown for evaluation only; the pipeline never reads it."


def _jsonl(rel):
    return {r["receipt_id"]: r for r in map(json.loads, (ROOT / rel).read_text(encoding="utf-8").splitlines()) if r}


def _app(receipt=None, page=None):
    at = AppTest.from_file(str(APP), default_timeout=30)
    if receipt:
        at.query_params["receipt"] = receipt
    at.run()
    if page:
        at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, at.exception
    return at


def _text(at):
    return " ".join(str(e.value) for e in [*at.markdown, *at.info, *at.warning, *at.header, *at.subheader])


def test_receipts_page_counts_and_banner():
    at = _app()
    assert BANNER in _text(at)
    m = {x.label: x.value for x in at.metric}
    assert (m["Scored"], m["Out of scope"]) == ("28", "4")
    assert len(at.dataframe[0].value) == 32


def test_mismatch_filter_matches_data():
    report, gold = _jsonl("output/report.jsonl"), _jsonl("data_eval/gold.jsonl")
    oos = {"RCP-020", "RCP-021", "RCP-029", "RCP-030"}
    mismatches = {r for r in report if r not in oos and report[r]["disposition"] != gold[r]["labels"]["disposition"]}
    at = _app()
    at.checkbox[0].check().run()
    assert set(at.dataframe[0].value["receipt"]) == mismatches


def test_out_of_scope_matches_answer_key_module():
    from validator.gold import OUT_OF_SCOPE  # the test may import it; the app may not

    tree = ast.parse(APP.read_text())
    consts = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "OUT_OF_SCOPE"]
    assert ast.literal_eval(consts[0]) == OUT_OF_SCOPE


@pytest.mark.parametrize("rid", ["RCP-016", "RCP-022", "RCP-023", "RCP-020"])
def test_detail_deep_link_shows_system_and_answer_key(rid):
    report, gold = _jsonl("output/report.jsonl"), _jsonl("data_eval/gold.jsonl")
    at = _app(receipt=rid)
    text = _text(at)
    assert rid in text and "Correct answer (answer key)" in text
    assert f"**Expected disposition:** `{gold[rid]['labels']['disposition']}`" in text
    for e in report[rid]["exceptions"]:
        assert f"**{e['rule_id']}**" in text
    expected_missing = {e["rule_id"] for e in gold[rid]["labels"]["expected_exceptions"]} - {e["rule_id"] for e in report[rid]["exceptions"]}
    for k in expected_missing:
        assert f"Missing exception **{k}**" in text
    if not expected_missing and report[rid]["disposition"] == gold[rid]["labels"]["disposition"]:
        assert "MISMATCH" not in text


def test_metrics_page_renders_confusion_and_eval():
    at = _app(page="Metrics")
    cm = at.dataframe[0].value
    report, gold = _jsonl("output/report.jsonl"), _jsonl("data_eval/gold.jsonl")
    oos = {"RCP-020", "RCP-021", "RCP-029", "RCP-030"}
    assert int(cm.values.sum()) == 28
    assert int(cm.loc["flag", "flag"]) == sum(r not in oos and report[r]["disposition"] == gold[r]["labels"]["disposition"] == "flag" for r in report)
    assert "Disposition accuracy" in _text(at)


def test_app_does_not_import_evaluator_modules():
    tree = ast.parse(APP.read_text())
    names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(m.startswith("validator") for m in names), names
