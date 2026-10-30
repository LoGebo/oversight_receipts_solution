import json

import pytest

from validator import run

from conftest import RECEIPTS, Fake, line, reply


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    path = tmp_path / "in.jsonl"
    path.write_text("".join(json.dumps(RECEIPTS[r]) + "\n" for r in ("RCP-001", "RCP-028")), encoding="utf-8")
    args = ["--receipts", str(path), "--out", str(tmp_path / "out"), "--cache", str(tmp_path / "cache")]
    fake = Fake(reply(*(line(f"RCP-001-L{i}") for i in (1, 2, 3)), line("RCP-001-L4", "service_fee")),
                reply(line("RCP-028-L1", "health_otc"), line("RCP-028-L2", "health_otc")))
    return args, fake, tmp_path / "out"


def test_writes_jsonl_and_md_then_reruns_from_cache_without_a_key(setup, capsys):
    args, fake, out = setup
    assert run.main(args, client=fake) == 0 and len(fake.calls) == 2
    reports = [json.loads(x) for x in (out / "report.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(r["receipt_id"], r["disposition"]) for r in reports] == [("RCP-001", "pass"), ("RCP-028", "review")]
    md = (out / "report.md").read_text(encoding="utf-8")
    assert "## RCP-028 — REVIEW" in md and "MCC-02" in md
    assert "pass 1, review 1, flag 0" in capsys.readouterr().out

    run.main(args)  # warm cache, no key, no client: nothing is called
    assert "calls 0, cache hits 2 | spend $0.0000" in capsys.readouterr().out


def test_md_shows_the_english_rendering_of_non_english_lines_only(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    path = tmp_path / "in.jsonl"
    path.write_text("".join(json.dumps(RECEIPTS[r]) + "\n" for r in ("RCP-008", "RCP-028")), encoding="utf-8")
    fake = Fake(reply(line("RCP-008-L1", en="Nicoise salad"), line("RCP-008-L2", en="Mineral water 50cl"),
                      line("RCP-008-L3", en="Espresso coffee")),
                reply(line("RCP-028-L1", "health_otc", en="EN-COPY"), line("RCP-028-L2", "health_otc")))
    assert run.main(["--receipts", str(path), "--out", str(tmp_path / "out"), "--cache", str(tmp_path / "c")], client=fake) == 0
    md = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "Salade nicoise (en: Nicoise salad)" in md and "EN-COPY" not in md and "Rules considered: " in md
    rows = [json.loads(x) for x in (tmp_path / "out" / "report.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["line_items"][0]["description_raw"] == "Salade nicoise"
    assert rows[1]["line_items"][0]["description_en"] == "EN-COPY"  # the jsonl keeps it for every line


def test_any_classifier_failure_exits_non_zero_and_writes_nothing(setup):
    args, _, out = setup
    one_fails = Fake(RuntimeError("x"), RuntimeError("x"),
                     reply(line("RCP-028-L1", "health_otc"), line("RCP-028-L2", "health_otc")))
    with pytest.raises(SystemExit, match="classifier failed for 1 of 2 receipt") as e:
        run.main(args, client=one_fails)
    assert e.value.code != 0 and not (out / "report.jsonl").exists()


def test_cache_miss_without_a_key_stops_with_a_message(setup):
    args, _, out = setup
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY is not set and 2 receipt"):
        run.main(args)
    assert not (out / "report.jsonl").exists()


def test_openrouter_rows_and_summary_carry_provider_model_and_reported_spend(setup, capsys):
    from test_openrouter import OR, chat
    args, _, out = setup
    fake = OR(chat(reply(*(line(f"RCP-001-L{i}") for i in (1, 2, 3)), line("RCP-001-L4", "service_fee")), cost=0.0011),
              chat(reply(line("RCP-028-L1", "health_otc"), line("RCP-028-L2", "health_otc")), cost=0.0022))
    assert run.main([*args, "--provider", "openrouter"], client=fake.client) == 0
    rows = [json.loads(x) for x in (out / "report.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {(r["provider"], r["model"]) for r in rows} == {("openrouter", "anthropic/claude-haiku-5.5")}
    assert "provider openrouter model anthropic/claude-haiku-5.5 | calls 2, cache hits 0 | spend $0.0033" in capsys.readouterr().out
    run.main([*args, "--provider", "openrouter"])  # warm cache, no key: no network
    assert "calls 0, cache hits 2 | spend $0.0000" in capsys.readouterr().out


def test_openrouter_cache_miss_without_its_key_names_that_key(setup, monkeypatch):
    args, _, _ = setup
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unused")  # the explicit flag wins over the default
    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY is not set and 2 receipt"):
        run.main([*args, "--provider", "openrouter"])


def test_md_table_cells_escape_pipes_and_newlines():
    r = {**RECEIPTS["RCP-028"]}
    r["line_items"] = [{**r["line_items"][0], "description_raw": "Lozenges | 24ct\nhoney"}, r["line_items"][1]]
    rep = {"receipt_id": "RCP-028", "disposition": "review", "exceptions": [], "review_signals": [], "superseded": [],
           "rules_considered": [], "line_items": [{"line_id": li["line_id"], "description_raw": li["description_raw"],
                                                   "amount_usd": li["amount_usd"], "category": "health_otc"}
                                                  for li in r["line_items"]]}
    md = run.to_markdown([rep], {"RCP-028": r})
    (row,) = [x for x in md.splitlines() if x.startswith("| RCP-028-L1 ")]
    assert row.startswith("| RCP-028-L1 | Lozenges \\| 24ct honey | ") and row.count(" | ") == 5


# ---- guard: the committed output/ is never rewritten by a run that is not the committed cache's ----

@pytest.fixture
def committed(tmp_path, monkeypatch):
    """run.ROOT pointed at a temp dir holding a sentinel output/report.jsonl; returns the sentinel path."""
    monkeypatch.setattr(run, "ROOT", tmp_path)
    for k in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / "output").mkdir()
    sentinel = tmp_path / "output" / "report.jsonl"
    sentinel.write_text("COMMITTED", encoding="utf-8")
    return sentinel


def _inp(tmp_path):
    path = tmp_path / "in.jsonl"
    path.write_text(json.dumps(RECEIPTS["RCP-028"]) + "\n", encoding="utf-8")
    return ["--receipts", str(path), "--cache", str(tmp_path / "cache")]


@pytest.mark.parametrize("extra", [["--provider", "openrouter"], ["--model", "other-model"]])
def test_default_out_refuses_other_provider_or_model(committed, tmp_path, extra):
    with pytest.raises(SystemExit, match="Pass --out"):
        run.main([*_inp(tmp_path), *extra], client=Fake())
    assert committed.read_text(encoding="utf-8") == "COMMITTED"


def test_openrouter_key_only_defaults_to_cache_only_anthropic_and_never_calls(committed, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    with pytest.raises(SystemExit, match="cache-only"):  # cache miss under the default out: no live call, nothing written
        run.main(_inp(tmp_path))
    assert committed.read_text(encoding="utf-8") == "COMMITTED"


def test_default_out_ignores_an_api_key_on_a_miss(committed, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake = Fake(reply(line("RCP-028-L1", "health_otc"), line("RCP-028-L2", "health_otc")))
    with pytest.raises(SystemExit, match="cache-only"):
        run.main(_inp(tmp_path), client=fake)
    assert not fake.calls and committed.read_text(encoding="utf-8") == "COMMITTED"


def test_default_out_still_runs_offline_from_a_warm_cache(committed, tmp_path):
    args = _inp(tmp_path)
    fake = Fake(reply(line("RCP-028-L1", "health_otc"), line("RCP-028-L2", "health_otc")))
    run.main([*args, "--out", str(tmp_path / "x")], client=fake)
    assert run.main(args) == 0 and committed.read_text(encoding="utf-8") != "COMMITTED"


def test_explicit_out_allows_openrouter(committed, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    args = [*_inp(tmp_path), "--out", str(tmp_path / "x")]
    with pytest.raises(SystemExit, match="classifier failed"):  # provider openrouter was chosen: it tried (and failed) live
        run.main(args, client=Fake())
    assert committed.read_text(encoding="utf-8") == "COMMITTED"
