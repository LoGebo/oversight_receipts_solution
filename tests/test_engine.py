import pytest

from validator import engine
from validator.engine import EXPECTED, run_engine
from validator.rules import health, lines, merchant

from conftest import CASES, MEAL, RECEIPTS, cats


def one(rid, **kw):
    return run_engine([RECEIPTS[rid]], cats(rid, *CASES[rid][0]), **kw)[rid]


def fired(result):
    return {c.rule_id: c.line_ids for c in result.checks if c.status == "fired"}


@pytest.mark.parametrize("rid", CASES)
def test_end_to_end_disposition_and_full_coverage(rid):
    res = one(rid)
    assert res.error is None and res.disposition == CASES[rid][1]
    assert sorted(c.rule_id for c in res.checks) == sorted(EXPECTED)


def test_specific_findings():
    assert fired(one("RCP-001")) == {}
    assert fired(one("RCP-026")) == {"TECH-02": ("RCP-026-L1",)}
    assert fired(one("RCP-028")) == {"MCC-02": ()}  # $14.48 OTC on a trip: HEALTH-01 does not fire


def test_apac_alcohol_supersession_counted_once():
    res = one("RCP-016")
    assert fired(res) == {"REG-01": ("RCP-016-L2",)}
    status = {c.rule_id: c.status for c in res.checks}
    assert [status[r] for r in ("ALC-01", "ALC-02", "ALC-03", "MEAL-01")] == ["superseded"] * 4


def test_cross_receipt_results_attached_to_each_receipt():
    rs = [RECEIPTS["RCP-020"], with_("RCP-021", merchant_name="Brass Kettle")]  # same employee, same day: $74 + $71.50 > $75
    out = run_engine(rs, {**cats("RCP-020", *MEAL), **cats("RCP-021", *MEAL)})
    assert all(fired(out[r]) == {"MEAL-01": ()} and out[r].disposition == "flag" for r in out)
    alone = run_engine(rs[:1], cats("RCP-020", *MEAL))["RCP-020"]
    assert alone.disposition == "pass"


def test_missing_rule_family_is_an_error_not_a_pass(monkeypatch):
    monkeypatch.setattr(merchant, "merchant_checks", lambda _: [])
    with pytest.raises(RuntimeError, match=r"coverage broken.*MCC-01"):
        one("RCP-001")


def test_duplicate_rule_is_a_coverage_error(monkeypatch):
    real = merchant.merchant_checks
    monkeypatch.setattr(merchant, "merchant_checks", lambda r: real(r) * 2)
    with pytest.raises(RuntimeError, match="coverage broken"):
        one("RCP-001")


def errs(result):
    return {c.rule_id for c in result.checks if c.rule_id.startswith("ERR-")}


def test_raising_rule_costs_only_its_family_on_that_receipt():
    rs = [RECEIPTS["RCP-001"], RECEIPTS["RCP-026"]]
    c = {**cats("RCP-001", *MEAL), **cats("RCP-026", "computer_accessory", "computer_accessory")}
    bad = {**rs[1], "line_items": [{**rs[1]["line_items"][0], "quantity": 0}, rs[1]["line_items"][1]]}
    out = run_engine([rs[0], bad], c)
    res = out["RCP-026"]
    assert res.disposition == "review" and errs(res) == {"ERR-lines"} and fired(res) == {"ERR-lines": ()}
    assert "quantity must be a positive int" in res.error and res.error.startswith("lines: ValueError")
    assert {i for i in (c.rule_id for c in res.checks)} == (EXPECTED - set(lines.RULE_IDS)) | {"ERR-lines"}
    assert out["RCP-001"].disposition == "pass" and out["RCP-001"].error is None


def test_raising_cross_receipt_family_keeps_every_other_family(monkeypatch):
    def boom(*_):
        raise KeyError("RCP-001-L9")
    monkeypatch.setattr(health, "health_checks", boom)
    out = run_engine([RECEIPTS["RCP-001"], RECEIPTS["RCP-026"]],
                     {**cats("RCP-001", *MEAL), **cats("RCP-026", "computer_accessory", "computer_accessory")})
    assert all(errs(r) == {"ERR-health"} and "health: KeyError" in r.error for r in out.values())
    assert out["RCP-001"].disposition == "review"
    assert out["RCP-026"].disposition == "flag" and "TECH-02" in fired(out["RCP-026"])


def test_raising_per_receipt_family_is_an_err_signal_not_a_coverage_error(monkeypatch):
    def boom(*_):
        raise ValueError("bad mcc")
    monkeypatch.setattr(merchant, "merchant_checks", boom)
    res = one("RCP-026")
    assert errs(res) == {"ERR-merchant"} and res.disposition == "flag" and res.error == "merchant: ValueError: bad mcc"


def test_failed_family_with_a_partial_result_is_still_a_coverage_error(monkeypatch):
    monkeypatch.setattr(health, "health_checks", lambda *_: {})
    with pytest.raises(RuntimeError, match=r"coverage broken.*HEALTH-01"):
        one("RCP-001")


ALC_RCP011 = cats("RCP-011", "alcohol", "food_beverage")  # Client Entertainment at a liquor store: ALC-03 + MCC-01
GOV_RCP022 = {"RCP-022-L1": ("government_official", "R. Delgado"), "RCP-022-L2": ("government_official", "R. Delgado")}


def with_(rid, **fields):
    return {**RECEIPTS[rid], **fields}


@pytest.mark.parametrize("fields, err", [
    (dict(employee_country="ZZ"), "ERR-MEAL-01"),                 # GLOBAL, no home currency known: MEAL-01 alone
    (dict(employee_country="FR", entity="EMEA"), "ERR-REG-03"),   # USD receipt, no EUR receipt that day
    (dict(attendee_count=True), None),                           # alcohol, meals all refuse it
    (dict(attendee_count=0), None),
])
def test_bad_receipt_still_flags_its_real_exceptions(fields, err):
    out = run_engine([with_("RCP-011", **fields), RECEIPTS["RCP-001"]], {**ALC_RCP011, **cats("RCP-001", *MEAL)})
    res = out["RCP-011"]
    assert res.disposition == "flag" and res.error and "MCC-01" in fired(res)
    assert err is None or err in errs(res)
    assert out["RCP-001"].disposition == "pass" and out["RCP-001"].error is None


def test_bad_attendee_count_is_refused_by_alcohol_too():
    res = run_engine([with_("RCP-011", mcc="5812", attendee_count=2.5)], ALC_RCP011)["RCP-011"]
    assert {"ERR-alcohol", "ERR-meals"} <= errs(res) and "attendee_count" in res.error


@pytest.mark.parametrize("fields", [dict(employee_country="DE", entity="EMEA"), dict(total_amount_usd=None)])
def test_gift04_critical_survives_a_failing_family(fields):
    res = run_engine([with_("RCP-022", **fields)], cats("RCP-022", "food_beverage", "gift"), gift_for=GOV_RCP022)["RCP-022"]
    assert res.disposition == "flag" and errs(res) and fired(res)["GIFT-04"] == ("RCP-022-L1", "RCP-022-L2")
    assert next(c for c in res.checks if c.rule_id == "GIFT-04").severity == "critical"


def test_bad_receipt_degrades_only_its_own_meal_day():
    c = {**cats("RCP-020", *MEAL), **cats("RCP-021", *MEAL), **cats("RCP-001", *MEAL)}
    out = run_engine([RECEIPTS["RCP-020"], with_("RCP-021", attendee_count=0), RECEIPTS["RCP-001"]], c)
    assert errs(out["RCP-020"]) == errs(out["RCP-021"]) == {"ERR-meals", "ERR-timing"}  # same employee, merchant, day
    assert out["RCP-020"].disposition == "review"
    assert out["RCP-001"].disposition == "pass" and out["RCP-001"].error is None


def test_bad_receipt_degrades_only_its_own_trip():
    c = {**cats("RCP-001", "health_otc", *MEAL[1:]), **cats("RCP-028", "health_otc", "health_otc")}
    first = RECEIPTS["RCP-001"]["line_items"]
    bad = {**RECEIPTS["RCP-001"], "trip_id": "TRIP-0248", "line_items": [{**first[0], "amount_usd": "1"}, *first[1:]]}
    out = run_engine([bad, RECEIPTS["RCP-028"], RECEIPTS["RCP-026"]],
                     {**c, **cats("RCP-026", "computer_accessory", "computer_accessory")})
    assert "ERR-health" in errs(out["RCP-028"]) and "ERR-health" in errs(out["RCP-001"])
    assert errs(out["RCP-026"]) == set() and out["RCP-026"].disposition == "flag"


def test_missing_date_does_not_crash_and_doc02_fires():
    rs = [with_("RCP-003", transaction_datetime=None), RECEIPTS["RCP-006"]]  # both E-1067
    c = {**cats("RCP-003", "computer_accessory", "office_supplies", "office_supplies"), **cats("RCP-006", "computer_accessory")}
    out = run_engine(rs, c)
    assert fired(out["RCP-003"]) == {"DOC-02": ()} and out["RCP-003"].disposition == "flag"
    assert next(c for c in out["RCP-003"].checks if c.rule_id == "DOC-02").severity == "medium"
    assert out["RCP-006"].disposition == "pass" and out["RCP-006"].error is None


def test_receipts_without_employee_are_never_pooled():  # $74 + $71.50 would breach $75 if pooled
    rs = [with_("RCP-020", employee_id=None), with_("RCP-021", employee_id=None)]
    out = run_engine(rs, {**cats("RCP-020", *MEAL), **cats("RCP-021", *MEAL)})
    assert all(r.disposition == "pass" and r.error is None for r in out.values())


def test_same_day_is_the_full_date_not_the_month():
    rs = [RECEIPTS["RCP-020"], with_("RCP-021", transaction_datetime="2026-04-28T19:40:00")]
    out = run_engine(rs, {**cats("RCP-020", *MEAL), **cats("RCP-021", *MEAL)})
    assert all(r.disposition == "pass" for r in out.values())


def test_lowercase_currency_is_domestic():  # 'usd' is USD: $75 cap, so $74 + $71.50 fires
    rs = [with_("RCP-020", currency=" usd"), with_("RCP-021", currency="usd", merchant_name="Brass Kettle")]
    out = run_engine(rs, {**cats("RCP-020", *MEAL), **cats("RCP-021", *MEAL)})
    assert all(fired(r) == {"MEAL-01": ()} and "(domestic)" in next(c.detail for c in r.checks if c.rule_id == "MEAL-01")
               for r in out.values())


def test_duplicate_receipt_ids_raise():
    with pytest.raises(ValueError, match="duplicate"):
        run_engine([RECEIPTS["RCP-001"], RECEIPTS["RCP-001"]], cats("RCP-001", *MEAL))


def eur(rid, day, rate, cur="EUR"):
    return {"receipt_id": rid, "currency": cur, "fx_rate_to_usd": rate, "transaction_datetime": f"{day}T10:00:00"}


def test_country_with_a_known_currency_is_no_longer_an_error():
    out = run_engine([with_("RCP-011", employee_country="MX"), RECEIPTS["RCP-001"]], {**ALC_RCP011, **cats("RCP-001", *MEAL)})
    assert out["RCP-011"].error is None and "(international)" in next(
        c.detail for c in out["RCP-011"].checks if c.rule_id == "MEAL-01")  # an MX employee paying USD


def gbp_rcp001():  # RCP-001 as a GB employee's GBP receipt at 1.25: lines 22.40 + 6.40 + 3.60 + 6.16 = GBP 38.56 = $48.20
    gbp = {"RCP-001-L1": 22.4, "RCP-001-L2": 6.4, "RCP-001-L3": 3.6, "RCP-001-L4": 6.16}
    return with_("RCP-001", employee_country="GB", entity="EMEA", currency="GBP", fx_rate_to_usd=1.25, total_amount=38.56,
                 line_items=[{**li, "amount": gbp[li["line_id"]]} for li in RECEIPTS["RCP-001"]["line_items"]])


def test_non_eur_emea_receipt_without_a_euro_rate_loses_only_reg03_and_reg04():
    res = run_engine([gbp_rcp001()], cats("RCP-001", *MEAL))["RCP-001"]
    assert fired(res) == {"ERR-REG-03": (), "ERR-REG-04": ()} and res.disposition == "review"
    st = {c.rule_id: c.status for c in res.checks}
    assert (st["REG-05"], st["DOC-04"], st["MEAL-01"], st["MEAL-02"]) == ("not_fired", "not_fired", "superseded", "not_fired")
    assert "no EUR->USD rate on the transaction date for this GBP receipt" in res.error


def test_non_eur_emea_receipt_uses_the_batchs_euro_rate_that_day():  # $48.20 vs EUR 70 x 1.08; EUR 44.63 vs EUR 50
    eur = with_("RCP-008", transaction_datetime="2026-04-14T12:00:00")
    out = run_engine([gbp_rcp001(), eur], {**cats("RCP-001", *MEAL), **cats("RCP-008", *MEAL[:3])})
    st = {c.rule_id: c.status for c in out["RCP-001"].checks}
    assert out["RCP-001"].error is None and (st["REG-03"], st["REG-04"]) == ("not_fired", "not_fired")


def test_missing_mcc_never_calls_alcohol_retail():
    res = run_engine([with_("RCP-011", mcc=None)], ALC_RCP011)["RCP-011"]
    st = {c.rule_id: c.status for c in res.checks}
    assert [st[r] for r in ("ALC-01", "ALC-02", "ALC-03")] == ["not_applicable"] * 3
    assert fired(res) == {"ERR-input": ()} and res.disposition == "review" and res.error == "input: no MCC recorded"


def test_eur_usd_is_the_one_euro_rate_of_that_date():
    r = eur("X", "2026-04-23", None, "USD")
    assert engine._eur_usd(r, [eur("A", "2026-04-23", 1.08)]) == 1.08
    assert engine._eur_usd(r, [eur("A", "2026-04-23", 1.08), eur("B", "2026-04-23", 1.08)]) == 1.08
    assert engine._eur_usd(r, [eur("A", "2026-04-23", 1.08), eur("B", "2026-04-23", 1.09)]) is None  # they disagree
    assert engine._eur_usd(r, [eur("A", "2026-04-24", 1.08)]) is None                                # other day
    assert engine._eur_usd(r, [eur("A", "2026-04-02", 1.08)]) is None                                # same month only
    assert engine._eur_usd(r, [eur("A", "2026-04-23", 1.08, " eur")]) == 1.08                        # normalised
    assert engine._eur_usd(r, [eur("A", "2026-04-23", 1.08, None), eur("B", "2026-04-23", None)]) is None
    assert engine._eur_usd({**r, "transaction_datetime": None}, [eur("A", "2026-04-23", 1.08)]) is None


def test_uncertain_on_non_itemized_is_an_err_signal_and_the_rules_still_run():
    res = run_engine([RECEIPTS["RCP-023"]], cats("RCP-023", "other"), uncertain={"RCP-023": {"RCP-023-L1"}})["RCP-023"]
    assert errs(res) == {"ERR-exc03"} and "EXC-03" not in {c.rule_id for c in res.checks}
    assert "DOC-01" in fired(res) and res.disposition == "flag"


def test_uncertain_lines_are_left_out_of_the_day_total():  # RCP-021's lines all uncertain: $74 alone
    c = {**cats("RCP-020", *MEAL), **cats("RCP-021", *MEAL)}
    unsure = {f"RCP-021-L{i}" for i in range(1, 5)}
    out = run_engine([RECEIPTS["RCP-020"], RECEIPTS["RCP-021"]], c, uncertain={"RCP-021": unsure})
    assert fired(out["RCP-020"]) == {} and fired(out["RCP-021"]) == {"EXC-03": tuple(sorted(unsure))}


def test_empty_uncertain_set_is_not_fired():
    res = run_engine([RECEIPTS["RCP-001"]], cats("RCP-001", *MEAL), uncertain={"RCP-001": set()})["RCP-001"]
    assert res.disposition == "pass" and res.error is None


def test_missing_category_fails_closed():
    res = run_engine([RECEIPTS["RCP-001"]], {})["RCP-001"]
    assert res.disposition == "review" and "KeyError" in res.error and "ERR-alcohol" in errs(res)


def test_uncertain_line_raises_exc03_and_is_left_out_of_every_rule():
    # the $329 monitor (L1) would fire TECH-02; uncertain, it is left out and only EXC-03 remains
    c = cats("RCP-026", "computer_accessory", "computer_accessory")
    res = run_engine([RECEIPTS["RCP-026"]], c, uncertain={"RCP-026": {"RCP-026-L1"}})["RCP-026"]
    assert fired(res) == {"EXC-03": ("RCP-026-L1",)} and res.disposition == "review"


def test_default_exc03_is_not_fired():
    res = one("RCP-001")
    assert next(c for c in res.checks if c.rule_id == "EXC-03").status == "not_fired"


def test_uncertain_on_unknown_line_or_receipt():
    with pytest.raises(ValueError):
        run_engine([RECEIPTS["RCP-001"]], cats("RCP-001", *MEAL), uncertain={"RCP-999": set()})
    res = run_engine([RECEIPTS["RCP-001"]], cats("RCP-001", *MEAL), uncertain={"RCP-001": {"RCP-002-L1"}})
    assert res["RCP-001"].disposition == "review" and "not on RCP-001" in res["RCP-001"].error


def test_gift_hook_is_sliced_per_receipt():
    rid = "RCP-022"
    hook = {f"{rid}-L1": ("government_official", "R. Delgado"), f"{rid}-L2": ("government_official", "R. Delgado")}
    res = run_engine([RECEIPTS[rid]], cats(rid, "food_beverage", "gift"), gift_for=hook)[rid]
    assert fired(res) == {"GIFT-04": (f"{rid}-L1", f"{rid}-L2")} and res.disposition == "flag"
    with pytest.raises(ValueError, match="unknown lines"):
        run_engine([RECEIPTS[rid]], cats(rid, "food_beverage", "gift"), gift_for={"X-L1": ("client", None)})


def test_gift_hook_for_one_receipt_leaves_the_others_alone():
    rs = [RECEIPTS["RCP-022"], RECEIPTS["RCP-001"]]
    out = run_engine(rs, {**cats("RCP-022", "food_beverage", "gift"), **cats("RCP-001", *MEAL)}, gift_for=GOV_RCP022)
    assert "GIFT-04" in fired(out["RCP-022"])
    assert out["RCP-001"].disposition == "pass" and out["RCP-001"].error is None


def test_emea_day_total_spans_the_employees_receipts():  # $49.68 + $37.80 = $87.48 > EUR 70 x 1.08, neither alone
    rs = [with_("RCP-008", attendee_count=None),
          with_("RCP-025", employee_id="E-2201", transaction_datetime="2026-04-23T19:15:00")]
    c = {**cats("RCP-008", "food_beverage", "food_beverage", "food_beverage"), **cats("RCP-025", *MEAL[:3])}
    out = run_engine(rs, c)
    assert all(fired(r) == {"REG-03": ()} and r.error is None for r in out.values())
    assert all(fired(run_engine([r], c)[r["receipt_id"]]) == {} for r in rs)


def test_unusable_uncertain_set_leaves_every_line_to_the_rules():
    c = cats("RCP-026", "computer_accessory", "computer_accessory")
    res = run_engine([RECEIPTS["RCP-026"]], c, uncertain={"RCP-026": {"RCP-001-L1"}})["RCP-026"]
    assert errs(res) == {"ERR-exc03"} and fired(res)["TECH-02"] == ("RCP-026-L1",) and res.disposition == "flag"


def test_retriever_miss_is_an_err_signal_on_that_receipt_only(monkeypatch):
    real = engine.retriever.candidate_rules
    monkeypatch.setattr(engine.retriever, "candidate_rules",
                        lambda r, *a: {} if r["receipt_id"] == "RCP-026" else real(r, *a))
    out = run_engine([RECEIPTS["RCP-026"], RECEIPTS["RCP-001"]],
                     {**cats("RCP-026", "computer_accessory", "computer_accessory"), **cats("RCP-001", *MEAL)})
    res = out["RCP-026"]
    assert fired(res) == {"TECH-02": ("RCP-026-L1",), "ERR-retriever": ()} and res.disposition == "flag"
    assert res.error == "retriever: missed rule TECH-02 (fired, not a candidate)"
    assert out["RCP-001"].disposition == "pass" and out["RCP-001"].error is None


def input_issue(**fields):
    return engine._input_issues({**RECEIPTS["RCP-001"], **fields})


def test_input_integrity_signal_never_fires_on_the_real_inputs():
    from pathlib import Path

    from validator.loader import load_receipts
    root = Path(__file__).resolve().parents[1]
    for p in ("data_split", "data_heldout"):
        assert {r["receipt_id"]: engine._input_issues(r)
                for r in load_receipts(root / p / "receipts_input.jsonl") if engine._input_issues(r)} == {}


def test_input_integrity_issues():  # RCP-001: USD at 1.0, lines 28.00 + 8.00 + 4.50 + 7.70 = $48.20 = total
    lines = RECEIPTS["RCP-001"]["line_items"]
    assert input_issue() == []
    assert input_issue(line_items=[]) == ["itemized receipt with no line items"]
    assert input_issue(mcc=None) == ["no MCC recorded"] and input_issue(mcc=" ") == ["no MCC recorded"]
    assert input_issue(total_amount_usd=float("nan")) == ["total_amount_usd is not a number: nan"]
    assert input_issue(total_amount="48.2") == ["total_amount is not a number: '48.2'"]
    assert input_issue(total_amount=True) == ["total_amount is not a number: True"]
    neg = [{**lines[0], "amount": -28.0, "amount_usd": -28.0}, *lines[1:]]  # a refund line: -28 + 20.20 = -7.80
    assert input_issue(line_items=neg, total_amount=-7.8, total_amount_usd=-7.8) == [
        "total_amount is negative: -7.8", "total_amount_usd is negative: -7.8",
        "RCP-001-L1 amount is negative: -28.0", "RCP-001-L1 amount_usd is negative: -28.0"]
    assert input_issue(total_amount_usd=48.68, total_amount=48.68) == []  # $0.48 off the lines, within 1% of $48.68
    assert input_issue(total_amount_usd=48.69, total_amount=48.69) == ["line amount_usd sum to 48.20, total_amount_usd is 48.69"]
    off = [{**lines[0], "amount_usd": 28.30}, *lines[1:]]                   # $0.30 off 28.00 x 1.0, 1% is $0.28
    assert input_issue(line_items=off, total_amount_usd=48.5) == ["RCP-001-L1 amount_usd 28.3 != amount 28.0 x rate 1.0"]
    small = [{**lines[2], "amount": 1.0, "amount_usd": 1.03}]               # $0.03 off $1.00: over the $0.02 floor
    assert input_issue(line_items=small, total_amount=1.0, total_amount_usd=1.03) == [
        "RCP-001-L3 amount_usd 1.03 != amount 1.0 x rate 1.0"]
    assert input_issue(total_amount=47.0) == ["total_amount_usd 48.2 != total_amount 47.0 x rate 1.0"]


def test_input_integrity_signal_reviews_an_otherwise_clean_receipt():
    res = run_engine([with_("RCP-001", mcc=None)], cats("RCP-001", *MEAL))["RCP-001"]
    assert fired(res) == {"ERR-input": ()} and res.disposition == "review" and res.error == "input: no MCC recorded"
