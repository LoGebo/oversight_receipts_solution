import pytest

from validator.classifier import classify
from validator.engine import run_engine
from validator.evaluation import oracle
from validator.gold import OUT_OF_SCOPE, load_gold
from validator.reporter import report
from validator.retriever import candidate_rules
from validator.rules import timing
from validator.rules.timing import group_key, timing_checks

from conftest import MEAL, RECEIPTS, cats

H = ("high", ())


def rcp(rid, *lines, emp="E-1", merchant="Copper Skillet", when="2026-04-27T12:00:00", kind="Meals - Individual",
        attendees=None, entity="GLOBAL", country="US", currency="USD", itemized=True, total=None, trip="TRIP-1",
        fx=None, **extra):
    """lines: (category, amount_usd); line ids are <rid>-L1, ... `total` defaults to the sum of the lines."""
    items = [{"line_id": f"{rid}-L{i}", "amount_usd": ln[1]} for i, ln in enumerate(lines, 1)]
    r = {"receipt_id": rid, "employee_id": emp, "employee_country": country, "entity": entity, "merchant_name": merchant,
         "submitted_expense_type": kind, "transaction_datetime": when, "currency": currency, "fx_rate_to_usd": fx,
         "total_amount_usd": sum(ln[1] for ln in lines) if total is None else total, "attendee_count": attendees,
         "itemized": itemized, "trip_id": trip, "line_items": items, **extra}
    return r, {f"{rid}-L{i}": ln[0] for i, ln in enumerate(lines, 1)}


def run(*receipts, gift_for=None, eur_usd=None):
    rs, c = [r for r, _ in receipts], {k: v for _, x in receipts for k, v in x.items()}
    return timing_checks(rs, c, gift_for, eur_usd)


def check(out, rid, rule):
    return next(c for c in out[0][rid] if c.rule_id == rule)


def split(*receipts, **kw):
    """receipt_id -> TIME-03 (severity, lines) for the receipts where it fired."""
    out = run(*receipts, **kw)
    return {rid: (c.severity, c.line_ids) for rid, cs in out[0].items() for c in cs if c.rule_id == "TIME-03" and c.status == "fired"}


def test_four_checks_in_fixed_order():
    out, around = run(rcp("A", ("food_beverage", 10.0)))
    assert [c.rule_id for c in out["A"]] == list(timing.RULE_IDS)
    assert [c.status for c in out["A"]] == ["not_fired", "not_fired", "not_fired", "not_applicable"]
    assert around == {}


@pytest.mark.parametrize("clock, fires", [
    ("00:00:00", True), ("02:14:00", True), ("04:59:00", True), ("04:59:59", True),
    ("05:00:00", False), ("05:00:01", False), ("12:00:00", False), ("23:59:00", False), ("23:59:59", False),
])
def test_time01_window_is_midnight_up_to_not_including_five(clock, fires):
    c = check(run(rcp("A", ("food_beverage", 10.0), when=f"2026-05-07T{clock}")), "A", "TIME-01")
    assert c.status == ("fired" if fires else "not_fired") and c.kind == "signal" and c.severity is None


def test_time01_reads_the_clock_as_written_ignoring_any_offset():
    c = check(run(rcp("A", ("food_beverage", 10.0), when="2026-05-07T02:14:00+09:00")), "A", "TIME-01")
    assert c.status == "fired" and c.detail.startswith("02:14")


def test_time01_date_without_a_time_is_not_applicable():
    assert check(run(rcp("A", ("food_beverage", 10.0), when="2026-05-07")), "A", "TIME-01").status == "not_applicable"


@pytest.mark.parametrize("when", [None, "", "  "])
def test_missing_date_makes_the_time_rules_not_applicable(when):
    r = rcp("A", ("food_beverage", 10.0), when=when, trip_start="2026-05-01", trip_end="2026-05-03")
    out, _ = run(r)
    assert {c.rule_id: c.status for c in out["A"]} == {
        "TIME-01": "not_applicable", "TIME-02": "not_fired", "TIME-03": "not_applicable", "TIME-04": "not_applicable"}


@pytest.mark.parametrize("when", ["2026-13-40T10:00:00", "yesterday", 20260507])
def test_unparseable_date_raises(when):
    with pytest.raises((ValueError, TypeError)):
        run(rcp("A", ("food_beverage", 10.0), when=when))


@pytest.mark.parametrize("kind, trip, status", [
    ("Meals - Individual", None, "fired"), ("Lodging", None, "fired"), ("Travel - Other", None, "fired"),
    ("Meals - Individual", " ", "fired"), ("Lodging", "TRIP-9", "not_fired"),
    ("Meals - Team", None, "not_applicable"), ("Client Entertainment", None, "not_applicable"),
    ("Office Supplies", None, "not_applicable"),
])
def test_time02_individual_travel_expense_without_a_trip(kind, trip, status):
    c = check(run(rcp("A", ("food_beverage", 10.0), kind=kind, trip=trip)), "A", "TIME-02")
    assert c.status == status and c.kind == "signal" and c.severity is None


# TIME-03 meal cap: each at or below the cap, together strictly above it
@pytest.mark.parametrize("a, b, fires", [
    (74.0, 71.5, True), (75.0, 0.01, True), (40.0, 35.0, False), (75.01, 10.0, False), (75.0, 0.0, False),
])
def test_time03_meal_cap_domestic(a, b, fires):
    got = split(rcp("A", ("food_beverage", a)), rcp("B", ("food_beverage", b), when="2026-04-27T19:40:00"))
    assert got == ({"A": H, "B": H} if fires else {})


@pytest.mark.parametrize("entity, country, currency, fx, b, fires", [
    ("GLOBAL", "US", "EUR", 1.08, 40.0, False), ("GLOBAL", "US", "EUR", 1.08, 40.01, True),   # $100 international
    ("APAC", "JP", "JPY", 0.0067, 0.0, False), ("APAC", "JP", "JPY", 0.0067, 0.01, True),    # $60 under REG-02
    ("EMEA", "DE", "EUR", 1.08, 15.6, False), ("EMEA", "DE", "EUR", 1.08, 15.61, True),      # EUR 70 x 1.08 = $75.60
])
def test_time03_meal_cap_is_the_employees_cap(entity, country, currency, fx, b, fires):
    kw = dict(entity=entity, country=country, currency=currency, fx=fx)
    got = split(rcp("A", ("food_beverage", 60.0), **kw), rcp("B", ("food_beverage", b), **kw))
    assert got == ({"A": H, "B": H} if fires else {})


def test_time03_meal_cap_takes_the_higher_when_a_group_mixes_currencies():
    assert split(rcp("A", ("food_beverage", 60.0)), rcp("B", ("food_beverage", 40.0), currency="EUR", fx=1.08)) == {}


def test_time03_emea_non_eur_receipt_uses_the_callers_euro_rate():
    kw = dict(entity="EMEA", country="GB", currency="USD")
    assert split(rcp("A", ("food_beverage", 60.0), **kw), rcp("B", ("food_beverage", 15.61), **kw),
                 eur_usd={"A": 1.08, "B": 1.08}) == {"A": H, "B": H}
    out = run(rcp("A", ("food_beverage", 60.0), **kw), rcp("B", ("food_beverage", 15.61), **kw))  # no euro rate
    assert {rid: [(c.rule_id, c.status, c.kind) for c in cs if "TIME-03" in c.rule_id] for rid, cs in out[0].items()} == {
        "A": [("ERR-TIME-03", "fired", "signal")], "B": [("ERR-TIME-03", "fired", "signal")]}
    assert out[1] == {} and check(out, "A", "TIME-01").status == "not_fired"  # the other timing rules still run


def test_time03_unknown_home_country_is_an_err_signal_unless_another_split_fires():
    meals = [rcp("A", ("food_beverage", 60.0), country="ZZ"), rcp("B", ("food_beverage", 30.0), country="ZZ")]
    assert [c.rule_id for c in run(*meals)[0]["A"]] == ["TIME-01", "TIME-02", "ERR-TIME-03", "TIME-04"]
    unitemized = [rcp(x, ("other", 40.0), country="ZZ", itemized=False) for x in "AB"]  # $80 > $75 itemization split
    assert split(*unitemized) == {"A": H, "B": H}


def test_time03_home_currency_of_a_non_us_country():  # MX employee: MXN is domestic ($75), USD international ($100)
    kw = dict(country="MX", currency="MXN", fx=0.055)
    assert split(rcp("A", ("food_beverage", 40.0), **kw), rcp("B", ("food_beverage", 35.01), **kw)) == {"A": H, "B": H}
    kw["currency"] = "USD"
    assert split(rcp("A", ("food_beverage", 40.0), **kw), rcp("B", ("food_beverage", 35.01), **kw)) == {}


@pytest.mark.parametrize("b_attendees, b_amount, fires", [(None, 40.0, True), (2, 80.0, True), (2, 70.0, False)])
def test_time03_meal_cap_is_compared_per_person(b_attendees, b_amount, fires):
    got = split(rcp("A", ("food_beverage", 80.0), attendees=2), rcp("B", ("food_beverage", b_amount), attendees=b_attendees))
    assert got == ({"A": H, "B": H} if fires else {})  # $40 + $40 / $40 + $40 / $40 + $35 vs $75


def test_time03_meal_cap_counts_only_meal_receipts():
    office = rcp("C", ("office_supplies", 70.0), kind="Office Supplies")
    assert split(rcp("A", ("food_beverage", 74.0)), rcp("B", ("food_beverage", 71.5)), office) == {"A": H, "B": H}
    assert split(rcp("A", ("food_beverage", 74.0)), office) == {}


def test_a_lone_receipt_is_never_measured_for_a_split():  # its bad attendee count is MEAL-01's to report
    out, around = run(rcp("A", ("food_beverage", 10.0), attendees=0, when="2026-05-07T02:14:00"))
    assert [c.status for c in out["A"]] == ["fired", "not_fired", "not_fired", "not_applicable"] and around == {}


def test_time03_needs_the_same_merchant():
    assert split(rcp("A", ("food_beverage", 74.0)), rcp("B", ("food_beverage", 71.5), merchant="Brass Kettle")) == {}


@pytest.mark.parametrize("field, value", [("emp", "E-2"), ("when", "2026-04-28T12:00:00")])
def test_timing_runs_over_one_employees_day(field, value):
    with pytest.raises(ValueError, match="one employee's day"):
        run(rcp("A", ("food_beverage", 74.0)), rcp("B", ("food_beverage", 71.5), **{field: value}))


def test_time03_meal_cap_is_the_days_cap_across_merchants():  # a EUR meal elsewhere that day: $100 applies
    a, b = rcp("A", ("food_beverage", 60.0)), rcp("B", ("food_beverage", 40.0))
    assert split(a, b) == {"A": H, "B": H}
    assert split(a, b, rcp("C", ("food_beverage", 5.0), merchant="Brass Kettle", currency="EUR", fx=1.0)) == {}
    assert split(a, b, rcp("C", ("office_supplies", 5.0), merchant="Brass Kettle", currency="EUR", fx=1.0,
                           kind="Office Supplies")) == {"A": H, "B": H}  # not a meal receipt: cap stays $75


def test_time03_merchant_name_ignores_case_and_spaces_and_midnight_is_a_new_date():
    a = rcp("A", ("food_beverage", 74.0), when="2026-04-27T23:59:59")
    assert group_key(a[0]) == group_key(rcp("B", ("food_beverage", 1.0), merchant=" COPPER skillet ")[0])
    assert group_key(a[0]) != group_key(rcp("B", ("food_beverage", 1.0), when="2026-04-28T00:00:00")[0])


@pytest.mark.parametrize("field", ["employee_id", "merchant_name", "transaction_datetime"])
def test_time03_without_a_group_is_its_own_receipt(field):
    r, c = rcp("A", ("food_beverage", 74.0))
    r[field] = None if field != "merchant_name" else " "
    assert group_key(r) == ("receipt", "A")
    assert check(timing_checks([r], c), "A", "TIME-03").status == "not_applicable"


@pytest.mark.parametrize("a, b, fires", [(40.0, 36.0, True), (75.0, 0.01, True), (40.0, 35.0, False), (75.01, 1.0, False)])
def test_time03_itemization_threshold_when_every_receipt_is_non_itemized(a, b, fires):
    kw = dict(kind="Office Supplies", itemized=False)
    assert split(rcp("A", ("other", a), **kw), rcp("B", ("other", b), **kw)) == ({"A": H, "B": H} if fires else {})


def test_time03_itemization_split_needs_every_receipt_non_itemized():
    assert split(rcp("A", ("other", 40.0), kind="Office Supplies", itemized=False),
                 rcp("B", ("office_supplies", 36.0), kind="Office Supplies")) == {}


GIFTS = dict(kind="Client Gifts", trip=None)


@pytest.mark.parametrize("b, fires", [(20.01, True), (20.0, False)])
def test_time03_gift_cap_for_one_recipient(b, fires):
    hook = {"A-L1": ("client", "J. Park"), "B-L1": ("client", "j. park ")}
    out, around = run(rcp("A", ("gift", 30.0), **GIFTS), rcp("B", ("gift", b), **GIFTS), gift_for=hook)
    assert {r for r, cs in out.items() if cs[2].status == "fired"} == ({"A", "B"} if fires else set())
    assert around == ({"A": ("gift cap",), "B": ("gift cap",)} if fires else {})


@pytest.mark.parametrize("hook", [
    {"A-L1": ("client", "J. Park"), "B-L1": ("client", "K. Lee")},           # two recipients
    {"A-L1": ("client", None), "B-L1": ("client", None)},                    # unnamed: not one recipient
    {},                                                                      # no hook
    {"A-L1": ("employee", "J. Park"), "B-L1": ("employee", "J. Park")},      # GIFT-03, not the client cap
])
def test_time03_gift_cap_needs_one_named_client(hook):
    assert split(rcp("A", ("gift", 30.0), **GIFTS), rcp("B", ("gift", 30.0), **GIFTS), gift_for=hook) == {}


def test_time03_gift_cap_leaves_out_gift_cards_and_food():
    hook = {"A-L1": ("client", "J. Park"), "B-L1": ("client", "J. Park")}
    for cat in ("gift_card", "food_beverage", "service_fee"):
        assert split(rcp("A", ("gift", 30.0), **GIFTS), rcp("B", (cat, 30.0), **GIFTS), gift_for=hook) == {}


def test_time03_reports_every_threshold_it_splits_around():
    kw = dict(itemized=False)
    out, around = run(rcp("A", ("other", 40.0), **kw), rcp("B", ("other", 36.0), **kw))
    assert around == {"A": ("itemization", "meal cap"), "B": ("itemization", "meal cap")}
    assert "DOC-01" in check((out, around), "A", "TIME-03").detail and "MEAL-01" in check((out, around), "A", "TIME-03").detail


TRIP = dict(trip_start="2026-05-04", trip_end="2026-05-08")  # Monday to Friday


@pytest.mark.parametrize("day, status", [
    ("2026-05-09", "fired"), ("2026-05-03", "fired"),            # Saturday after, Sunday before
    ("2026-05-08", "not_fired"), ("2026-05-11", "not_fired"),    # weekdays, in and out of the trip
])
def test_time04_weekend_outside_the_trip_dates(day, status):
    c = check(run(rcp("A", ("food_beverage", 10.0), when=f"{day}T12:00:00", **TRIP)), "A", "TIME-04")
    assert c.status == status and c.kind == "signal" and c.severity is None


def test_time04_trip_dates_are_inclusive():
    sat = dict(trip_start="2026-05-09", trip_end="2026-05-13")
    assert check(run(rcp("A", ("food_beverage", 10.0), when="2026-05-09T00:00:00", **sat)), "A", "TIME-04").status == "not_fired"
    trip = dict(trip_start="2026-05-04", trip_end="2026-05-09")
    assert check(run(rcp("A", ("food_beverage", 10.0), when="2026-05-09T23:59:59", **trip)), "A", "TIME-04").status == "not_fired"
    assert check(run(rcp("A", ("food_beverage", 10.0), when="2026-05-10T00:00:00", **trip)), "A", "TIME-04").status == "fired"


def test_time04_needs_a_trip_with_dates():
    assert check(run(rcp("A", ("food_beverage", 10.0), when="2026-05-09T12:00:00")), "A", "TIME-04").status == "not_applicable"
    no_trip = rcp("A", ("food_beverage", 10.0), when="2026-05-09T12:00:00", trip=None, **TRIP)
    assert check(run(no_trip), "A", "TIME-04").status == "not_applicable"
    with pytest.raises(ValueError, match="after trip_end"):
        run(rcp("A", ("food_beverage", 10.0), trip_start="2026-05-09", trip_end="2026-05-04"))


# engine, retriever, reporter and answer key, on the real receipts

def with_(rid, **fields):
    return {**RECEIPTS[rid], **fields}


def fired(result):
    return {c.rule_id: (c.severity, c.line_ids) for c in result.checks if c.status == "fired"}


def statuses(result):
    return {c.rule_id: c.status for c in result.checks}


SPLIT = {**cats("RCP-020", *MEAL), **cats("RCP-021", *MEAL)}


def test_real_split_reports_time03_and_supersedes_meal01():
    out = run_engine([RECEIPTS["RCP-020"], RECEIPTS["RCP-021"]], SPLIT)
    for res in out.values():
        assert fired(res) == {"TIME-03": H} and res.disposition == "flag" and res.error is None
        assert statuses(res)["MEAL-01"] == "superseded"
    assert run_engine([RECEIPTS["RCP-020"]], cats("RCP-020", *MEAL))["RCP-020"].disposition == "pass"


def test_emea_split_supersedes_reg03():  # $49.68 + $37.80 > EUR 70 x 1.08, neither alone
    rs = [with_("RCP-008", attendee_count=None),
          with_("RCP-025", employee_id="E-2201", transaction_datetime="2026-04-23T19:15:00", merchant_name="Le Petit Marche")]
    c = {**cats("RCP-008", "food_beverage", "food_beverage", "food_beverage"), **cats("RCP-025", *MEAL[:3])}
    for res in run_engine(rs, c).values():
        assert fired(res) == {"TIME-03": H} and statuses(res)["REG-03"] == "superseded" and statuses(res)["MEAL-01"] == "superseded"


def test_gift_only_split_leaves_the_meal_cap_rule_alone():
    # gifts $42 + $44 to one client: a split. Meals $32 + $27.50 at Copper Skillet are not, but with $48.20
    # elsewhere that day the day is over $75, so MEAL-01 stays a breach on all three.
    c = {**cats("RCP-020", "gift", *MEAL[1:]), **cats("RCP-021", "gift", *MEAL[1:]), **cats("RCP-001", *MEAL)}
    hook = {"RCP-020-L1": ("client", "J. Park"), "RCP-021-L1": ("client", "J. Park")}
    elsewhere = with_("RCP-001", employee_id="E-1180", transaction_datetime="2026-04-27T08:00:00")
    out = run_engine([RECEIPTS["RCP-020"], RECEIPTS["RCP-021"], elsewhere], c, gift_for=hook)
    for rid in ("RCP-020", "RCP-021"):
        assert fired(out[rid]) == {"TIME-03": H, "MEAL-01": ("medium", ())}
        assert "gift cap" in next(x.detail for x in out[rid].checks if x.rule_id == "TIME-03")
    assert fired(out["RCP-001"]) == {"MEAL-01": ("medium", ())}


def test_failed_timing_family_keeps_the_meal_breach(monkeypatch):
    def boom(*_):
        raise ValueError("boom")
    monkeypatch.setattr(timing, "timing_checks", boom)
    for res in run_engine([RECEIPTS["RCP-020"], RECEIPTS["RCP-021"]], SPLIT).values():
        assert fired(res) == {"MEAL-01": ("medium", ()), "ERR-timing": (None, ())} and res.disposition == "flag"


def test_bad_date_costs_only_its_timing_group():
    out = run_engine([with_("RCP-029", transaction_datetime="2026-05-07T25:00:00"), RECEIPTS["RCP-030"]],
                     {**cats("RCP-029", *MEAL[1:]), **cats("RCP-030", *MEAL[1:])})
    assert {"ERR-timing", "ERR-documentation"} <= fired(out["RCP-029"]).keys() and out["RCP-029"].disposition == "review"
    assert fired(out["RCP-030"]) == {"TIME-02": (None, ())} and out["RCP-030"].error is None


def test_missing_date_reports_doc02_and_no_timing():
    res = run_engine([with_("RCP-029", transaction_datetime=None)], cats("RCP-029", *MEAL[1:]))["RCP-029"]
    assert fired(res) == {"DOC-02": ("medium", ())} and res.error is None
    assert [statuses(res)[r] for r in ("TIME-01", "TIME-03", "TIME-04")] == ["not_applicable"] * 3


def test_retriever_names_time03_for_meal_non_itemized_and_named_gift_receipts():
    base = {"receipt_id": "T", "submitted_expense_type": "Office Supplies", "itemized": True, "line_items": [{"line_id": "T-L1"}]}
    assert "TIME-03" not in candidate_rules(base, {"T-L1": "gift"})
    assert "TIME-03" in candidate_rules({**base, "submitted_expense_type": "Meals - Team"}, {"T-L1": "other"})
    assert "TIME-03" in candidate_rules(base, {"T-L1": "gift"}, {"T-L1": ("client", "J. Park")})


def test_reporter_quotes_the_transaction_pattern_rules():
    out = run_engine([RECEIPTS["RCP-020"], RECEIPTS["RCP-021"]], SPLIT)
    rep = report(RECEIPTS["RCP-020"], out["RCP-020"])
    assert [(e["rule_id"], e["policy_doc"], e["severity"], e["line_ids"]) for e in rep["exceptions"]] == [
        ("TIME-03", "transaction-pattern-rules.md", "high", [])]
    assert rep["exceptions"][0]["evidence"].startswith("Two or more receipts by the same employee")
    assert [s["rule_id"] for s in rep["superseded"]] == ["MEAL-01"]
    res = run_engine([RECEIPTS["RCP-029"]], cats("RCP-029", *MEAL[1:]))["RCP-029"]
    rep = report(RECEIPTS["RCP-029"], res)
    assert rep["disposition"] == "review" and rep["exceptions"] == []
    assert [(s["rule_id"], s["policy_doc"]) for s in rep["review_signals"]] == [("TIME-01", "transaction-pattern-rules.md")]


class _NoNetwork:
    @property
    def messages(self):
        raise RuntimeError("cache miss")


def test_stretch_receipts_match_the_answer_key_with_the_committed_cache():
    receipts = list(RECEIPTS.values())
    c = classify(receipts, client=_NoNetwork())
    assert not c.meta["failures"], c.meta["failures"]
    results, gold = run_engine(receipts, c.categories, gift_for=c.gift_for, uncertain=c.uncertain), load_gold()
    assert oracle.compare(results, gold, stretch=True) == [] and oracle.compare(results, gold) == []
    assert {r: results[r].disposition for r in OUT_OF_SCOPE} == {
        "RCP-020": "flag", "RCP-021": "flag", "RCP-029": "review", "RCP-030": "review"}


def test_stretch_receipts_match_the_answer_key_under_the_oracle():
    results, gold = oracle.run()
    assert oracle.compare(results, gold, stretch=True) == []
