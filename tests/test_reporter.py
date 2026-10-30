import pytest

from validator import reporter
from validator.check import Check
from validator.classifier import RESTRICTED, Classification
from validator.engine import EXPECTED, Result, run_engine
from validator.reporter import POLICY_DIR, _rules, plain, policy_text, report

from conftest import CASES, RECEIPTS, cats


def classification(rid, band="high"):
    c = cats(rid, *CASES[rid][0])
    return Classification(c, {}, {}, {k: RESTRICTED[v] for k, v in c.items()},
                          {"model": "fake", "confidence": dict.fromkeys(c, band)})


def rep(rid):
    c = classification(rid)
    return report(RECEIPTS[rid], run_engine([RECEIPTS[rid]], c.categories)[rid], c)


def test_every_quote_is_verbatim_and_every_engine_rule_resolves():
    rules = _rules()
    for rid, (doc, _, text) in rules.items():
        assert text and text in (POLICY_DIR / doc).read_text(encoding="utf-8"), rid
    missing = EXPECTED - rules.keys()  # rule ids the engine can fire with no policy paragraph
    assert missing == set(), sorted(missing)
    assert policy_text("ALC-03") == ("meals-and-entertainment-policy.md", rules["ALC-03"][2])
    assert policy_text("ALC-03")[1].startswith("Alcohol purchased from a package store")
    with pytest.raises(KeyError):
        policy_text("NOPE-01")


@pytest.mark.parametrize("rid", CASES)
def test_disposition_and_evidence_guards(rid):
    out = rep(rid)
    assert out["receipt_id"] == rid and out["disposition"] == CASES[rid][1]
    assert [li["line_id"] for li in out["line_items"]] == [li["line_id"] for li in RECEIPTS[rid]["line_items"]]
    cats = classification(rid).categories
    ids = [e["rule_id"] for e in out["exceptions"] + out["review_signals"]]
    assert len(ids) == len(set(ids))
    for e in out["exceptions"]:
        assert e["evidence"] in plain((POLICY_DIR / e["policy_doc"]).read_text(encoding="utf-8"))
        assert e["evidence"] == plain(policy_text(e["rule_id"])[1]) and not {"*", "`", "\n"} & set(e["evidence"])
        assert e["severity"] and e["explanation"].startswith(e["rule_id"] + " (") and e["explanation"].endswith(".")
        assert all(cats[lid] != "service_fee" and lid.startswith(rid + "-") for lid in e["line_ids"])
        assert [x["line_id"] for x in e["lines"]] == e["line_ids"]


def test_pass_has_nothing():
    out = rep("RCP-001")
    assert out["exceptions"] == out["review_signals"] == [] and out["model"] == "fake"
    assert out["line_items"][0] | {"confidence": 0.9} == out["line_items"][0]
    assert not any("category_detail" in li or "category_note" in li for li in out["line_items"])


def test_flag_cites_the_monitor():
    (e,) = rep("RCP-026")["exceptions"]
    assert (e["rule_id"], e["severity"], e["line_ids"], e["policy_doc"]) == (
        "TECH-02", "medium", ["RCP-026-L1"], "technology-and-equipment-policy.md")


def test_explanation_is_a_sentence_naming_the_items_amounts_and_reason():
    (e,) = rep("RCP-026")["exceptions"]
    assert e["explanation"] == ("TECH-02 (Peripherals under $200) raises a medium exception on '27-inch 4K UHD monitor' "
                                "($329.00): unit prices RCP-026-L1 $329.00, RCP-026-L2 $14.99 vs $200 per item; "
                                "no pre-approval reference.")
    res = Result("RCP-023", "flag", (Check("DOC-01", "fired", severity="medium", detail="$186.0 vs $75, itemized=False"),))
    (e,) = report(RECEIPTS["RCP-023"], res)["exceptions"]
    assert e["explanation"] == (f"DOC-01 (Itemization threshold) raises a medium exception on the receipt from "
                                f"{RECEIPTS['RCP-023']['merchant_name']} ($186.00 total): $186.0 vs $75, itemized=False.")


def test_bare_category_details_read_as_a_reason():
    lid = RECEIPTS["RCP-028"]["line_items"]
    out = report(RECEIPTS["RCP-028"], run_engine([RECEIPTS["RCP-028"]], cats("RCP-028", "tobacco", "personal_electronics"))["RCP-028"])
    got = {e["rule_id"]: e["explanation"] for e in out["exceptions"]}
    assert got["PERS-03"] == (f"PERS-03 (Tobacco and vaping) raises a high exception on '{lid[0]['description_raw']}' "
                              f"(${lid[0]['amount_usd']:.2f}): categorised tobacco.")
    assert got["TECH-01"].endswith(": categorised personal_electronics.")


def test_plain_drops_markdown_and_line_breaks():
    assert plain("A **high**\n`other`  *item*.") == "A high other item."
    assert "**" in policy_text("ALC-01")[1] and plain(policy_text("ALC-01")[1]).startswith(
        "Alcohol is reimbursable only on a receipt declared as Client Entertainment")


def test_apac_override_reports_reg01_not_alc():
    out = rep("RCP-016")
    assert [(e["rule_id"], e["line_ids"]) for e in out["exceptions"]] == [("REG-01", ["RCP-016-L2"])]
    assert out["exceptions"][0]["policy_doc"] == "regional-addendum.md"
    assert {"ALC-01", "ALC-02", "ALC-03"} <= {s["rule_id"] for s in out["superseded"]}


def test_signal_only_is_review_with_mcc02_and_no_exceptions():
    out = rep("RCP-028")
    assert out["disposition"] == "review" and out["exceptions"] == []
    assert [(s["rule_id"], s["policy_doc"]) for s in out["review_signals"]] == [("MCC-02", "merchant-category-risk.md")]
    assert "5912" in out["review_signals"][0]["reason"]


@pytest.mark.parametrize("disp, shown", [("pass", "review"), ("review", "review"), ("flag", "flag")])
def test_error_never_passes_and_never_hides_a_flag(disp, shown):
    out = report(RECEIPTS["RCP-001"], Result("RCP-001", disp, error="ValueError: boom"))
    assert out["disposition"] == shown and out["error"] == "ValueError: boom" and out["exceptions"] == []


def test_no_error_key_without_an_error():
    assert "error" not in rep("RCP-001")


def _fired(rid, *line_ids):
    return Result(rid, "flag", (Check("TECH-01", "fired", severity="high", line_ids=line_ids),))


def test_refuses_a_line_from_another_receipt():
    with pytest.raises(ValueError, match="not on the receipt"):
        report(RECEIPTS["RCP-001"], _fired("RCP-001", "RCP-002-L1"))


def test_refuses_to_cite_a_tip_line():
    with pytest.raises(ValueError, match="EXC-04"):
        report(RECEIPTS["RCP-001"], _fired("RCP-001", "RCP-001-L4"), classification("RCP-001"))


def test_refuses_a_duplicate_rule():
    dup = Result("RCP-001", "flag", _fired("RCP-001").checks * 2)
    with pytest.raises(ValueError, match="more than once"):
        report(RECEIPTS["RCP-001"], dup)


def test_refuses_a_result_for_another_receipt():
    with pytest.raises(ValueError, match="not for receipt"):
        report(RECEIPTS["RCP-001"], Result("RCP-002", "pass"))


def test_err_signal_is_a_review_signal_with_the_error_and_no_policy_doc():
    r = RECEIPTS["RCP-026"]
    bad = {**r, "line_items": [{**r["line_items"][0], "quantity": 0}, r["line_items"][1]]}
    c = classification("RCP-026")
    out = report(bad, run_engine([bad], c.categories)["RCP-026"], c)
    (s,) = [s for s in out["review_signals"] if s["rule_id"] == "ERR-lines"]
    assert s["policy_doc"] is None and "quantity must be a positive int" in s["reason"] and s["line_ids"] == []
    assert out["disposition"] == "review" and "lines: ValueError" in out["error"]


def test_error_does_not_hide_a_flag():
    res = Result("RCP-026", "flag", (Check("TECH-01", "fired", severity="high"),), error="lines: ValueError: x")
    assert report(RECEIPTS["RCP-026"], res)["disposition"] == "flag"


@pytest.mark.parametrize("band, value, shown", [("high", 0.9, "high"), ("medium", 0.7, "medium"), ("low", 0.3, "low"),
                                                ("rule", 1.0, "rule"), (None, 0.0, "failed")])
def test_confidence_band_to_number(band, value, shown):
    c = classification("RCP-028")
    meta = {"confidence": {} if band is None else dict.fromkeys(c.categories, band)}
    c = Classification(c.categories, {}, {}, c.restricted, meta)
    row = report(RECEIPTS["RCP-028"], run_engine([RECEIPTS["RCP-028"]], c.categories)["RCP-028"], c)["line_items"][0]
    assert (row["confidence"], row["confidence_band"]) == (value, shown)


def test_signal_keeps_its_line_ids_and_policy_doc():
    res = Result("RCP-028", "review", (Check("EXC-03", "fired", "signal", line_ids=("RCP-028-L1",), detail="unsure"),))
    (s,) = report(RECEIPTS["RCP-028"], res)["review_signals"]
    assert s == {"rule_id": "EXC-03", "policy_doc": policy_text("EXC-03")[0], "reason": "unsure", "line_ids": ["RCP-028-L1"]}


def test_superseded_is_context_not_an_exception():
    res = Result("RCP-001", "pass", (Check("ALC-01", "superseded", detail="by REG-01"),))
    out = report(RECEIPTS["RCP-001"], res)
    assert out["superseded"] == [{"rule_id": "ALC-01", "reason": "by REG-01"}] and out["exceptions"] == []


def test_a_rule_defined_in_two_policy_documents_is_refused(tmp_path, monkeypatch):
    for name in ("a.md", "b.md"):
        (tmp_path / name).write_text("**ABC-01 — Title.** Some text.\n", encoding="utf-8")
    monkeypatch.setattr(reporter, "POLICY_DIR", tmp_path)
    _rules.cache_clear()
    try:
        with pytest.raises(ValueError, match="ABC-01 is defined in both a.md and b.md"):
            _rules()
    finally:
        monkeypatch.undo()
        _rules.cache_clear()


def test_line_fields_translation_and_rules_considered():
    c = classification("RCP-028")
    c = Classification(c.categories, {}, {}, c.restricted, c.meta, {"RCP-028-L1": "Throat lozenges"}, {})
    out = report(RECEIPTS["RCP-028"], run_engine([RECEIPTS["RCP-028"]], c.categories)["RCP-028"], c)
    assert out["line_items"][0]["description_en"] == "Throat lozenges" and "description_en" not in out["line_items"][1]
    assert "category_note" not in out["line_items"][0]
    considered = {x["rule_id"]: x["policy_doc"] for x in out["rules_considered"]}
    assert considered["HEALTH-01"] == policy_text("HEALTH-01")[0] and considered["MCC-02"] == "merchant-category-risk.md"
    assert "TECH-02" not in considered and considered.keys() <= EXPECTED


def test_extension_is_reported_as_other_unrestricted_with_its_detail_and_note():
    cats = {"RCP-009-L1": "mobile_handset"}
    c = Classification(cats, {}, {}, {"RCP-009-L1": False}, {"confidence": {"RCP-009-L1": "high"}}, {},
                       {"RCP-009-L1": "an iPhone"})
    (row,) = report(RECEIPTS["RCP-009"], run_engine([RECEIPTS["RCP-009"]], cats)["RCP-009"], c)["line_items"]
    assert (row["category"], row["category_detail"], row["restricted"], row["category_note"]) == (
        "other", "mobile_handset", False, "an iPhone")


def test_rule_set_category_reports_confidence_one():
    cats = {"RCP-023-L1": "other"}
    c = Classification(cats, {}, {}, {"RCP-023-L1": False}, {"confidence": {"RCP-023-L1": "rule"}}, {},
                       {"RCP-023-L1": "non-itemized charge: contents unknown"})
    (row,) = report(RECEIPTS["RCP-023"], run_engine([RECEIPTS["RCP-023"]], cats)["RCP-023"], c)["line_items"]
    assert (row["confidence"], row["confidence_band"], row["category_note"]) == (
        1.0, "rule", "non-itemized charge: contents unknown")
    assert "category_detail" not in row
