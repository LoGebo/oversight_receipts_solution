"""scripts/compare_models.py with a fake OpenRouter client: no network, no key."""
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location("compare_models", Path(__file__).resolve().parents[1] / "scripts" / "compare_models.py")
cm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cm)


def args(tmp_path, *extra):
    return ["--out", str(tmp_path / "out"), "--cache", str(tmp_path / "cache"), *extra]


def test_dry_run_prints_plan_and_estimate_and_writes_nothing(tmp_path, capsys):
    assert cm.main(args(tmp_path, "--dry-run")) == 0
    out = capsys.readouterr().out
    assert "anthropic/claude-sonnet-5.5" in out and "total" in out and "pipeline ok" in out
    assert not (tmp_path / "out").exists()
    assert cm.estimate("anthropic/claude-haiku-5.5") == pytest.approx((97_000 * 0.10 + 6_500 * 0.50) / 1e6)


def test_full_run_writes_per_model_dirs_and_summary(tmp_path):
    models = ["anthropic/claude-haiku-5.5", "qwen/qwen3.8-omni-flash"]
    assert cm.main(args(tmp_path, "--models", *models), client=cm.fake_client()) == 0
    for m in models:
        assert (tmp_path / "out" / cm.slug(m) / "report.jsonl").exists() and (tmp_path / "cache" / cm.slug(m)).is_dir()
    s = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    row = s["models"][0]
    assert row["disposition_acc"][1] == 28 and row["false_positives_of_pass"][1] == 9 and row["missed_of_flag"][1] == 16
    assert row["category_acc"][1] == 65 and row["failures"] == 0 and row["calls"] == 32
    md = (tmp_path / "out" / "SUMMARY.md").read_text(encoding="utf-8")
    assert "qwen/qwen3.8-omni-flash" in md and "Caveats" in md and "28 scored" in md


def test_model_without_structured_outputs_is_recorded_not_fatal(tmp_path):
    def handle(req):
        return httpx.Response(200, json={"data": {"endpoints": [{"supported_parameters": ["temperature"], "pricing": {}}]}})
    client = httpx.Client(base_url=cm.classifier.OPENROUTER_URL, transport=httpx.MockTransport(handle))
    assert cm.main(args(tmp_path, "--models", "x/no-json"), client=client) == 0
    row = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))["models"][0]
    assert row["failures"] == 32 and "structured outputs" in next(iter(row["failure_reasons"].values()))


def test_global_cap_skips_remaining_models(tmp_path):
    base = cm.fake_client()
    def pricey(req):
        r = base._transport.handle_request(req)
        if req.method == "POST":
            d = json.loads(r.read()); d["usage"]["cost"] = 0.1
            return httpx.Response(200, json=d)
        return r
    client = httpx.Client(base_url=cm.classifier.OPENROUTER_URL, transport=httpx.MockTransport(pricey))
    cm.main(args(tmp_path, "--models", "a/one", "b/two", "--cap", "0.05", "--budget", "1"), client=client)
    rows = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))["models"]
    assert rows[0]["spend_usd"] >= 0.05 and "cap" in rows[1]["skipped"]


def test_missing_key_stops_before_any_work(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY"):
        cm.main(args(tmp_path))
