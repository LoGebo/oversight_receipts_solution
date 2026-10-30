"""Evaluation maths and the frozen keyword baseline. No network, no key, no cache needed."""
import ast
import hashlib
import json
from pathlib import Path

import pytest

from validator import classifier
from validator.evaluation import baseline, evaluate
from validator.evaluation.evaluate import (_NoNetwork, bootstrap, clopper_pearson, disposition_discordance, f1_binary,
                                           macro_f1, mcnemar, measures, ppv, wilson)

from conftest import Fake, synthetic

# Frozen before the baseline was ever scored. Changing KEYWORDS or how they match changes these: that is the point.
BASELINE_SHA256 = "a06f11a10aa5e39bca25efdf5978fac91e4f51a848b5daeba4cc241569896994"
PATTERNS_SHA256 = "44302b5be9a629ef05b3693c74c7bbbd2128177d6db16a5a6ac003af02dba7d9"


@pytest.mark.parametrize("k,n,lo,hi", [
    (0, 10, 0.0, 0.30850), (10, 10, 0.69150, 1.0), (5, 10, 0.18709, 0.81291),  # published CP values
    (0, 9, 0.0, 0.33627), (0, 16, 0.0, 0.20591),
])
def test_clopper_pearson_known_values(k, n, lo, hi):
    got = clopper_pearson(k, n)
    assert got == pytest.approx((lo, hi), abs=5e-5)


@pytest.mark.parametrize("k,n,lo,hi", [(5, 10, 0.23659, 0.76341), (0, 10, 0.0, 0.27753), (0, 9, 0.0, 0.29915)])
def test_wilson_known_values(k, n, lo, hi):
    assert wilson(k, n) == pytest.approx((lo, hi), abs=5e-5)


def test_intervals_reject_bad_counts():
    for bad in ((1, 0), (-1, 5), (6, 5)):
        with pytest.raises(ValueError):
            clopper_pearson(*bad)
        with pytest.raises(ValueError):
            wilson(*bad)


def mean(s):
    return sum(s) / len(s)


def test_bootstrap_is_deterministic_with_its_seed():
    units = [0, 1, 1, 0, 1, 1, 1, 0, 1, 1]
    assert bootstrap(units, mean, b=2000, seed=7) == bootstrap(units, mean, b=2000, seed=7)
    lo, hi = bootstrap(units, mean, b=2000, seed=7)
    assert 0 <= lo < 0.7 < hi <= 1
    assert bootstrap([1] * 5, mean, b=100) == (1.0, 1.0)


def test_bootstrap_takes_the_2_5_and_97_5_percentiles():
    # seed 2, 41 resample means of 0..9, sorted: [1.9, 2.8, 3.0, ..., 6.2, 6.3, 6.7]; indices round(0.025 * 40) = 1, 39
    assert bootstrap(list(range(10)), mean, b=41, seed=2) == pytest.approx((2.8, 6.3))
    # seed 1, 21 means: [3.0, ..., 6.1, 6.2]; round(0.025 * 20) = 0 and round(0.975 * 20) = round(19.5) = 20
    assert bootstrap(list(range(10)), mean, b=21, seed=1) == pytest.approx((3.0, 6.2))


def test_ppv_hand_computed():
    # sens = spec = 0.9 at 3%: 0.027 / (0.027 + 0.097) = 0.21774
    assert ppv(0.9, 0.9, 0.03) == pytest.approx(0.027 / 0.124)
    assert ppv(0.75, 10 / 12, 0.03) == pytest.approx(0.0225 / (0.0225 + 0.97 / 6))
    assert ppv(1.0, 1.0, 0.03) == 1.0


def test_f1_scores_hand_computed():
    assert macro_f1([("a", "a"), ("a", "b"), ("b", "b")]) == pytest.approx(2 / 3)
    assert macro_f1([("a", "a"), ("a", "b")]) == pytest.approx(2 / 3)  # b is predicted but not in the answers: not averaged
    assert macro_f1([("a", "b"), ("b", "b")]) == pytest.approx((0 + 2 / 3) / 2)  # never-predicted class scores 0
    assert f1_binary([(True, True), (True, False), (False, True), (False, False)]) == pytest.approx(0.5)


def test_mcnemar_exact():
    assert mcnemar(0, 0) == 1.0
    assert mcnemar(7, 0) == pytest.approx(2 * 0.5 ** 7)


def test_no_network_client_refuses():
    with pytest.raises(RuntimeError, match="cache miss"):
        _NoNetwork().messages  # noqa: B018


def test_baseline_keyword_table_and_matching_are_frozen():
    got = hashlib.sha256(json.dumps(baseline.KEYWORDS, ensure_ascii=False).encode()).hexdigest()
    assert got == BASELINE_SHA256, "baseline.KEYWORDS changed after it was frozen and scored"
    patterns = [(c, rx.pattern) for c, rx in baseline._COMPILED]
    got = hashlib.sha256(json.dumps(patterns, ensure_ascii=False).encode()).hexdigest()
    assert got == PATTERNS_SHA256, "baseline matching changed after it was frozen and scored"


@pytest.mark.parametrize("text,cat", [
    ("Heineken beer", "alcohol"), ("Box of cigars", "tobacco"), ("Noise-cancelling headphones", "personal_electronics"),
    ("Gift card $50", "gift_card"), ("Paper towels", "household_goods"), ("Haircut", "personal_care"),
    ("Casino chips", "gambling"), ("USB-C cable", "computer_accessory"), ("Taxi to airport", "ground_transport"),
    ("Dry cleaning", "laundry_service"), ("Cough lozenges", "health_otc"), ("Gratuity", "service_fee"),
    ("Room charge", "lodging"), ("ビール", "alcohol"), ("Kopfhörer", "personal_electronics"), ("zzz", "other"),
    ("ginger tea", "food_beverage"), ("Gin & tonic", "alcohol"), ("BEER", "alcohol"), ("缶ビール", "alcohol"),
])
def test_baseline_maps_taxonomy_words(text, cat):
    assert baseline.classify_line(text) == cat


def test_baseline_non_itemized_is_other():
    r = {"itemized": False, "line_items": [{"line_id": "X-L1", "description_raw": "beer"}]}
    assert baseline.classify([r]) == {"X-L1": "other"}


def test_baseline_never_reads_the_answers():
    src = Path(baseline.__file__).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            assert not any("gold" in n or "loader" in n for n in names), names
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "gold" not in node.value.lower() and "receipts.jsonl" not in node.value


def test_measures_hand_computed():
    results, gold, cats = synthetic()
    m = measures(results, cats, gold)
    assert m["ok"] == {"T-1": False, "T-2": True, "T-3": False}
    assert dict(m["confusion"]) == {("pass", "review"): 1, ("flag", "flag"): 1, ("flag", "review"): 1}
    k = {key: (m[key]["k"], m[key]["n"]) for key in m if isinstance(m[key], dict) and "k" in m[key]}
    assert k == {
        "disposition": (1, 3), "fp_of_pass": (1, 1), "missed_of_flag": (1, 2),
        "flag_precision": (1, 1), "flag_recall": (1, 2), "review_precision": (0, 2), "review_recall": (0, 0),
        "pass_precision": (0, 0), "pass_recall": (0, 1), "sens_flag": (1, 2), "spec_flag": (1, 1),
        "sens_any": (2, 2), "spec_any": (0, 1),
        "exc_precision": (1, 2), "exc_recall": (1, 2), "evidence_exact": (0, 1),
        "sig_precision": (1, 3), "sig_recall": (1, 1),
        "cat_acc": (2, 4), "restricted_acc": (2, 4)}
    assert m["errors"] == 1 and m["exc03_signals"] == 1
    assert m["per_rule"] == {"ALC-01": (1, 1, 1), "GIFT-04": (0, 0, 1), "TECH-01": (0, 1, 0)}
    # food_beverage 2/3, alcohol 2/3, gift 0 (the mobile_handset refinement is scored as `other`)
    assert m["macro_f1"] == pytest.approx(4 / 9) and m["n_classes"] == 3
    assert m["restricted_f1"] == pytest.approx(0.5)
    assert [x[2] for x in m["lines"]] == ["food_beverage", "alcohol", "alcohol", "other"]
    assert m["disposition_boot"][0] <= 1 / 3 <= m["disposition_boot"][1]
    assert "lines" not in measures(results, None, gold)


def test_discordance_counts_each_direction():
    ms = {"A LLM": {"ok": {"r1": True, "r2": True, "r3": False, "r4": True}},
          "C KEYWORD": {"ok": {"r1": False, "r2": False, "r3": True, "r4": True}}}
    assert disposition_discordance(ms) == (2, 1)


def test_keyword_better_respects_the_direction_of_each_measure():
    a = {key: {"p": 0.5} for _, key, _ in evaluate.MEASURES_HIGHER}
    c = {**a, "disposition": {"p": 0.6}, "fp_of_pass": {"p": 0.4}, "missed_of_flag": {"p": 0.9}, "macro_f1": 0.4}
    assert evaluate.keyword_better(a, c) == ["disposition accuracy", "false positives"]


def test_pct_and_fmt():
    assert evaluate.pct(None) == evaluate.pct(float("nan")) == "n/a" and evaluate.pct(0.5) == "50.0%"
    assert evaluate.fmt(evaluate.prop(0, 0)) == "0/0 (n/a)"
    assert evaluate.fmt(evaluate.prop(5, 10), True) == "5/10 = 50.0% [18.7%, 81.3%] W[23.7%, 76.3%]"


def test_cache_miss_exits_without_calling(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)  # empty cache: every receipt misses
    with pytest.raises(SystemExit, match="cache misses") as e:
        evaluate.run_systems()
    assert e.value.code != 0


def test_failed_calls_exit_even_when_calls_are_allowed(tmp_path, monkeypatch):
    real = evaluate.classify
    fake = Fake(*[RuntimeError("API down")] * 64)
    monkeypatch.setattr(evaluate, "classify", lambda receipts, **kw: real(receipts, **{**kw, "client": fake}))
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="classifier failures") as e:
        evaluate.run_systems(allow_calls=True)
    assert e.value.code != 0 and fake.calls


def test_heldout_failure_case_is_computed_from_the_record_and_the_engine():
    rec = json.loads(evaluate.HELDOUT["v2"].read_text(encoding="utf-8"))
    f = evaluate.heldout_failures(rec, evaluate.load_receipts(evaluate.HELDOUT_INPUT))
    assert [x["line_id"] for x in f["wrong"]] == ["HO-008-L4", "HO-011-L5", "HO-017-L2", "HO-021-L2", "HO-026-L4"]
    assert {x["confidence"] for x in f["wrong"]} == {"medium"}  # none low: EXC-03 catches none
    assert [x["line_id"] for x in f["flips"]] == ["HO-008-L4", "HO-011-L5"]
    assert f["by_category"] == {"HO-008": "PERS-01 cites HO-008-L1, HO-008-L2 instead of HO-008-L1, HO-008-L2, HO-008-L4",
                                "HO-011": "review -> flag, LAUNDRY-01 no longer fires, PERS-01 fires on HO-011-L5",
                                "HO-017": "PERS-02 no longer fires"}
    assert [x["line_id"] for x in f["spurious"]] == ["HO-004-L1", "HO-018-L2"]
    assert f["by_recipient"] == {"HO-018": "GIFT-01 cites HO-018-L1, HO-018-L2 instead of HO-018-L1"}
    assert f["gift04_if_official"] == ["HO-004-L1", "HO-018-L2"]


def test_case2_without_heldout_data_says_so():
    assert "not computed" in evaluate.case2({}, None)[0]


def test_heldout_before_after_compares_the_last_two_runs():
    def rec(v, *preds):  # line i expects "gift"; preds are the predicted categories
        rows = [{"line_id": f"H-L{i}", "description_raw": f"item {i}", "expected": "gift", "predicted": p, "exact": p == "gift",
                 "acceptable": p == "gift", "ambiguous": False, "confidence": "medium", "gift_expected": None, "gift_got": None}
                for i, p in enumerate(preds, 1)]
        return {"meta": {"model": "m", "prompt_version": v, "calls": 1, "cost_usd": 0.0}, "lines": rows}
    out = "\n".join(evaluate.heldout_section({"v1": rec("v1", "other", "other"), "v2": rec("v2", "gift", "other"),
                                               "v3": rec("v3", "gift", "gift")}))
    assert "v2 -> v3: exact category 1/2 -> 2/2" in out and "used to choose between prompts" in out
    assert "| H-L2 | item 2 | gift | other (medium) | gift (medium) |" in out and "| v2 | v3 |" in out
    assert "| H-L1 |" not in out  # right in both v2 and v3, though v1 had it wrong


def test_committed_eval_md_is_what_the_generator_writes(tmp_path, monkeypatch):
    out = tmp_path / "EVAL.md"
    monkeypatch.setattr(evaluate, "OUT", out)
    evaluate.main([])
    text = out.read_text(encoding="utf-8")
    assert text == (evaluate.ROOT / "output" / "EVAL.md").read_text(encoding="utf-8"), "rerun the generator"
    assert f"prompt {classifier.PROMPT_VERSION}" in text and text.count("**1. ") == text.count("**2. ") == 1
    assert "TIME family" not in text and "uncertainty route catches 3 of 7" in text


def test_report_prose_follows_the_measured_values():
    results, cats, extra, gold, receipts = evaluate.run_systems()
    ms = {s: measures(results[s], cats[s], gold) for s in evaluate.SYSTEMS}
    rid = next(r for r, ok in ms["B ORACLE"]["ok"].items() if ok)  # B gets it right: not a case-1 receipt
    ms["A LLM"]["ok"][rid] = False
    dated = [{**receipts[0], "trip_start": "2026-04-01", "trip_end": "2026-04-30"}, *receipts[1:]]
    text = evaluate.report(ms, results, {**extra, "gift_for": {}}, gold, dated, {}, None)
    n = len(evaluate.scored_ids(gold))
    assert f"A LLM gets 1 of the {n} scored receipts wrong ({rid}); case 1 is" in text and "A LLM gets none" not in text
    assert "Every category is right in B" not in text and "stated recipients the classifier returned on these receipts: none" in text
    assert "## What A's scores do and do not mean" in text and "What a score of 1.000" not in text
    assert "TIME-04 can apply to the 1 receipt(s)" in text and "TIME-04 never applies" not in text
