import pytest

from validator.check import verdict
from validator.loader import load_receipts
from validator.rules.meals import meal_checks

from conftest import cats


def rcp(rid, *lines, emp="E-1", day="2026-04-27", kind="Meals - Individual", attendees=None, entity="GLOBAL",
        country="US", currency="USD", itemized=True, total=None):
    """lines: (category, amount_usd); line ids are <rid>-L1, ... `total` defaults to the sum of the lines."""
    items = [{"line_id": f"{rid}-L{i}", "amount_usd": ln[1]} for i, ln in enumerate(lines, 1)]
    r = {"receipt_id": rid, "employee_id": emp, "employee_country": country, "entity": entity,
         "submitted_expense_type": kind, "transaction_datetime": f"{day}T12:00:00", "currency": currency,
         "total_amount_usd": sum(ln[1] for ln in lines) if total is None else total,
         "attendee_count": attendees, "itemized": itemized, "line_items": items}
    return r, {f"{rid}-L{i}": ln[0] for i, ln in enumerate(lines, 1)}


def run(*receipts):
    rs, cats = [r for r, _ in receipts], {k: v for _, c in receipts for k, v in c.items()}
    return meal_checks(rs, cats)


def fired(out):
    return {(rid, c.rule_id): (c.severity, c.line_ids) for rid, cs in out.items() for c in cs if c.status == "fired"}


def status(out, rule):
    return {rid: next(c.status for c in cs if c.rule_id == rule) for rid, cs in out.items()}


M = ("medium", ())


def test_three_checks_per_receipt_in_fixed_order():
    out = run(rcp("A", ("food_beverage", 10.0)), rcp("B", ("office_supplies", 10.0), kind="Office Supplies"))
    assert list(out) == ["A", "B"]
    assert all([c.rule_id for c in cs] == ["MEAL-01", "MEAL-02", "REG-02"] for cs in out.values())
    assert [c.status for c in out["B"]] == ["not_applicable"] * 3
    assert [c.status for c in out["A"]] == ["not_fired", "not_fired", "not_applicable"]


def test_missing_category_fails_closed():
    r, _ = rcp("A", ("food_beverage", 10.0))
    with pytest.raises(KeyError):
        meal_checks([r], {})


@pytest.mark.parametrize("bad", [0, -2, 2.0, "3", True])
def test_bad_attendee_count_raises(bad):
    with pytest.raises(ValueError):
        run(rcp("A", ("food_beverage", 10.0), attendees=bad))


def test_bad_itemized_raises():
    with pytest.raises(ValueError):
        run(rcp("A", ("food_beverage", 10.0), itemized="no"))


# --- What is a meal receipt ----------------------------------------------------------------------

@pytest.mark.parametrize("kind, expected", [("Meals - Individual", True), ("Meals - Team", True),
                                            ("Client Entertainment", True), ("Travel - Other", False), ("Lodging", False)])
def test_only_declared_meal_types_are_meal_receipts(kind, expected):
    out = run(rcp("A", ("food_beverage", 80.0), kind=kind))
    assert (("A", "MEAL-01") in fired(out)) is expected


def test_alcohol_alone_is_drink():  # a Client Entertainment bottle from a liquor store is a meal receipt
    assert fired(run(rcp("A", ("alcohol", 80.0), kind="Client Entertainment"))) == {("A", "MEAL-01"): M}


def test_itemized_without_food_or_drink_is_not_a_meal_receipt():  # a service fee alone is not food or drink
    out = run(rcp("A", ("service_fee", 90.0), ("gift", 200.0), kind="Meals - Team"))
    assert [c.status for c in out["A"]] == ["not_applicable"] * 3


def test_non_itemized_declared_meal_is_a_meal_receipt_and_uses_the_full_total():
    out = run(rcp("A", ("other", 80.0), itemized=False))
    assert fired(out) == {("A", "MEAL-01"): M} and "$80.00" in out["A"][0].detail


def test_non_itemized_ignores_line_amounts():  # total says $80, line says $10: the total wins
    assert fired(run(rcp("A", ("other", 10.0), itemized=False, total=80.0))) == {("A", "MEAL-01"): M}


# --- Meal spend ----------------------------------------------------------------------------------

def test_meal_spend_counts_food_drink_and_gratuity():  # 40 + 20 + 15.01 = 75.01
    assert fired(run(rcp("A", ("food_beverage", 40.0), ("alcohol", 20.0), ("service_fee", 15.01)))) == {("A", "MEAL-01"): M}


@pytest.mark.parametrize("cat", ["gift", "other", "tobacco", "household_goods"])
def test_other_lines_are_left_out(cat):  # $70 of food plus $500 of anything else stays under $75
    assert fired(run(rcp("A", ("food_beverage", 70.0), (cat, 500.0), attendees=1))) == {}


def test_itemized_spend_uses_lines_not_the_receipt_total():
    assert fired(run(rcp("A", ("food_beverage", 70.0), total=500.0))) == {("A", "MEAL-02"): ("low", ())}


# --- Cap boundaries (strictly above fires) -------------------------------------------------------

@pytest.mark.parametrize("usd, expected", [(74.99, False), (75.00, False), (75.01, True)])
def test_domestic_boundary(usd, expected):
    assert (("A", "MEAL-01") in fired(run(rcp("A", ("food_beverage", usd))))) is expected


@pytest.mark.parametrize("usd, expected", [(99.99, False), (100.00, False), (100.01, True)])
def test_international_boundary(usd, expected):  # US employee, EUR receipt
    assert (("A", "MEAL-01") in fired(run(rcp("A", ("food_beverage", usd), currency="EUR")))) is expected


# --- Per person ----------------------------------------------------------------------------------

@pytest.mark.parametrize("usd, expected", [(225.00, False), (225.03, True)])
def test_divided_by_attendee_count(usd, expected):  # 3 x $75 = $225
    assert (("A", "MEAL-01") in fired(run(rcp("A", ("food_beverage", usd), kind="Meals - Team", attendees=3)))) is expected


def test_attendee_count_of_one_is_not_special():
    assert ("A", "MEAL-01") in fired(run(rcp("A", ("food_beverage", 76.0), attendees=1)))


# --- Per day: one employee, one calendar date ----------------------------------------------------

def test_day_total_over_cap_fires_on_every_contributing_receipt():  # 40 + 35.01 = 75.01
    out = run(rcp("A", ("food_beverage", 40.0)), rcp("B", ("food_beverage", 35.01)), rcp("C", ("food_beverage", 1.0), day="2026-04-28"))
    assert fired(out) == {("A", "MEAL-01"): M, ("B", "MEAL-01"): M}
    assert "$75.01" in out["A"][0].detail and "$75" in out["A"][0].detail


@pytest.mark.parametrize("second, expected", [(35.00, False), (35.01, True)])
def test_day_total_boundary(second, expected):
    out = run(rcp("A", ("food_beverage", 40.0)), rcp("B", ("food_beverage", second)))
    assert set(fired(out)) == ({("A", "MEAL-01"), ("B", "MEAL-01")} if expected else set())


def test_day_sums_per_person_amounts():  # $120/2 + $20/1 = $80 > $75 (summing first then dividing would be $70)
    out = run(rcp("A", ("food_beverage", 120.0), kind="Meals - Team", attendees=2), rcp("B", ("food_beverage", 20.0)))
    assert set(fired(out)) == {("A", "MEAL-01"), ("B", "MEAL-01")}


def test_other_employee_same_day_is_not_mixed_in():
    out = run(rcp("A", ("food_beverage", 40.0)), rcp("B", ("food_beverage", 40.0), emp="E-2"))
    assert fired(out) == {}


def test_other_date_same_employee_is_not_mixed_in():
    out = run(rcp("A", ("food_beverage", 40.0)), rcp("B", ("food_beverage", 40.0), day="2026-04-28"))
    assert fired(out) == {}


def test_date_is_the_written_local_date_not_shifted():
    a, ca = rcp("A", ("food_beverage", 40.0))
    b, cb = rcp("B", ("food_beverage", 40.0), day="2026-04-28")
    a["transaction_datetime"], b["transaction_datetime"] = "2026-04-27T23:59:00", "2026-04-28T00:01:00"
    assert fired(meal_checks([a, b], {**ca, **cb})) == {}


def test_non_meal_receipt_same_day_does_not_contribute():
    out = run(rcp("A", ("food_beverage", 70.0)), rcp("B", ("food_beverage", 70.0), kind="Travel - Other"))
    assert fired(out) == {}


def test_mixed_day_uses_the_higher_cap():  # $50 USD + $40 EUR = $90: over $75, under $100
    out = run(rcp("A", ("food_beverage", 50.0)), rcp("B", ("food_beverage", 40.0), currency="EUR"))
    assert fired(out) == {} and "international" in out["A"][0].detail


def test_unknown_home_country_is_an_err_signal_for_meal01_only():
    out = run(rcp("A", ("food_beverage", 200.0), country="ZZ"))
    assert [(c.rule_id, c.status, c.kind) for c in out["A"]] == [
        ("ERR-MEAL-01", "fired", "signal"), ("MEAL-02", "fired", "exception"), ("REG-02", "not_applicable", "exception")]
    assert "'ZZ'" in out["A"][0].detail


@pytest.mark.parametrize("cur, amount, fires, which", [
    ("MXN", 75.00, False, "domestic"), ("MXN", 75.01, True, "domestic"),
    ("USD", 100.00, False, "international"), ("USD", 100.01, True, "international")])
def test_home_currency_of_a_non_us_employee(cur, amount, fires, which):  # MX: MXN is home, USD is abroad
    out = run(rcp("A", ("food_beverage", amount), country="MX", currency=cur))
    assert (out["A"][0].status == "fired") is fires and f"({which})" in out["A"][0].detail


def test_every_input_country_has_a_home_currency():
    from pathlib import Path

    from validator.rules.meals import HOME_CURRENCY
    root = Path(__file__).resolve().parents[1]
    countries = {r["employee_country"] for p in ("data_split", "data_heldout")
                 for r in load_receipts(root / p / "receipts_input.jsonl")}
    assert countries == {"US", "FR", "IN", "JP", "DE", "PT", "MX", "BR", "GB", "ES"} and countries <= HOME_CURRENCY.keys()
    assert (HOME_CURRENCY["MX"], HOME_CURRENCY["BR"], HOME_CURRENCY["GB"], HOME_CURRENCY["DE"]) == ("MXN", "BRL", "GBP", "EUR")


# --- MEAL-02: total above $150 needs an attendee count -------------------------------------------

@pytest.mark.parametrize("total, expected", [(150.00, False), (150.01, True)])
def test_meal02_boundary(total, expected):  # receipt total, not meal spend: the gift counts here
    out = run(rcp("A", ("food_beverage", 10.0), ("gift", total - 10.0)))
    assert fired(out) == ({("A", "MEAL-02"): ("low", ())} if expected else {})


def test_meal02_satisfied_by_any_recorded_count():
    out = run(rcp("A", ("food_beverage", 200.0), kind="Meals - Team", attendees=3))
    assert status(out, "MEAL-02") == {"A": "not_fired"}


def test_meal02_not_applicable_to_non_meal_receipts():
    assert status(run(rcp("A", ("lodging", 500.0), kind="Lodging")), "MEAL-02") == {"A": "not_applicable"}


def test_meal02_also_applies_to_apac():
    out = run(rcp("A", ("food_beverage", 20.0), ("gift", 140.0), entity="APAC", country="IN", currency="INR"))
    assert fired(out) == {("A", "MEAL-02"): ("low", ())}


# --- REG-02: APAC $60 per person, supersedes MEAL-01 ---------------------------------------------

def apac(rid, usd, **kw):
    return rcp(rid, ("food_beverage", usd), entity="APAC", country="JP", currency="JPY", **kw)


@pytest.mark.parametrize("usd, expected", [(59.99, False), (60.00, False), (60.01, True)])
def test_reg02_boundary(usd, expected):
    out = run(apac("A", usd))
    assert fired(out) == ({("A", "REG-02"): M} if expected else {})
    assert status(out, "MEAL-01") == {"A": "superseded"}


def test_reg02_replaces_the_international_figure_too():  # JPY employee, USD receipt: still $60
    out = run(rcp("A", ("food_beverage", 70.0), entity="APAC", country="JP", currency="USD"))
    assert fired(out) == {("A", "REG-02"): M}


def test_reg02_day_group_and_per_person():  # $90/3 + $30.01 = $60.01
    out = run(apac("A", 90.0, kind="Client Entertainment", attendees=3), apac("B", 30.01))
    assert fired(out) == {("A", "REG-02"): M, ("B", "REG-02"): M}


def test_apac_country_not_in_home_currency_map_is_fine():  # SG has no entry: APAC never needs it
    out = run(rcp("A", ("food_beverage", 10.0), entity="APAC", country="SG", currency="SGD"))
    assert status(out, "REG-02") == {"A": "not_fired"}


def test_emea_meal01_is_superseded_and_reg02_not_applicable():  # REG-03 (elsewhere) replaces MEAL-01
    out = run(rcp("A", ("food_beverage", 500.0), entity="EMEA", country="DE", currency="EUR"))
    assert [c.status for c in out["A"]] == ["superseded", "fired", "not_applicable"]  # MEAL-02 still applies


def test_global_reg02_is_not_applicable():
    assert status(run(rcp("A", ("food_beverage", 500.0))), "REG-02") == {"A": "not_applicable"}


def test_superseded_and_fired_receipt_verdict_has_no_duplicates():
    assert verdict(run(apac("A", 61.0))["A"]) == "flag"


# --- Real receipts, with categories written by hand (the answer key is not read) -----------------

F, A, S = "food_beverage", "alcohol", "service_fee"
REAL_CATS = {
    "RCP-001": [F, F, F, S], "RCP-002": [F, A, S], "RCP-004": [F, F, F, F], "RCP-007": [F, F, S],
    "RCP-008": [F, F, F], "RCP-010": [F, A, S], "RCP-011": [A, F], "RCP-015": [F, A, S], "RCP-016": [F, A, S],
    "RCP-020": [F, F, F, S], "RCP-021": [F, F, F, S], "RCP-022": [F, "gift"], "RCP-023": ["other"],
    "RCP-024": ["tobacco", F, F], "RCP-025": [F, A, F], "RCP-029": [F, F, S], "RCP-030": [F, F, S],
}


def real():
    rs = load_receipts()
    c = {li["line_id"]: "other" for r in rs for li in r["line_items"]}
    for rid, cs in REAL_CATS.items():
        c.update(cats(rid, *cs))
    return rs, meal_checks(rs, c)


def test_real_receipts():
    rs, out = real()
    assert len(out) == len(rs)
    # E-1180 on 2026-04-27: lunch $74.00 + dinner $71.50 = $145.50 > $75; RCP-015: $429.60 / 2 = $214.80 > $75
    assert fired(out) == {("RCP-020", "MEAL-01"): M, ("RCP-021", "MEAL-01"): M, ("RCP-015", "MEAL-01"): M}
    assert "$145.50" in out["RCP-020"][0].detail


def test_real_statuses():
    _, out = real()
    s = status(out, "MEAL-01")
    assert s["RCP-016"] == "superseded" and status(out, "REG-02")["RCP-016"] == "not_fired"  # 65.34/3 = $21.78
    assert s["RCP-008"] == s["RCP-025"] == "superseded"                                      # EMEA
    assert s["RCP-023"] == "not_fired" and "$62.00" in out["RCP-023"][0].detail             # non-itemized 186/3
    assert s["RCP-022"] == "not_fired" and "$34.00" in out["RCP-022"][0].detail             # gift left out: 68/2
    assert s["RCP-024"] == "not_fired" and "$9.00" in out["RCP-024"][0].detail              # tobacco left out
    assert s["RCP-011"] == "not_fired"                                                       # liquor store, drink only
    assert s["RCP-005"] == s["RCP-017"] == s["RCP-028"] == "not_applicable"                 # not meal types


# --- Exact arithmetic, grouping and currency normalisation ---------------------------------------

@pytest.mark.parametrize("third, expected", [(125.00, False), (125.01, True)])
def test_day_exactly_at_cap_in_thirds_does_not_fire(third, expected):  # 50/3 + 50/3 + 125/3 = $75.00 exactly
    out = run(*(rcp(x, ("food_beverage", usd), kind="Meals - Team", attendees=3) for x, usd in (("A", 50.0), ("B", 50.0), ("C", third))))
    assert (("A", "MEAL-01") in fired(out)) is expected


@pytest.mark.parametrize("third, expected", [(100.00, False), (100.01, True)])
def test_reg02_exactly_at_cap_in_thirds_does_not_fire(third, expected):  # 40/3 + 40/3 + 100/3 = $60.00
    out = run(*(apac(x, usd, kind="Meals - Team", attendees=3) for x, usd in (("A", 40.0), ("B", 40.0), ("C", third))))
    assert (("A", "REG-02") in fired(out)) is expected


@pytest.mark.parametrize("emp, when", [(None, "2026-04-27T12:00:00"), ("E-1", None), ("E-1", ""), ("E-1", "   ")])
def test_receipt_without_employee_or_date_is_its_own_day(emp, when):  # $40 + $40 pooled would breach $75
    a, ca = rcp("A", ("food_beverage", 40.0), emp=emp)
    b, cb = rcp("B", ("food_beverage", 40.0), emp=emp)
    a["transaction_datetime"] = b["transaction_datetime"] = when
    out = meal_checks([a, b], {**ca, **cb})
    assert fired(out) == {} and "= $40.00 per person" in out["A"][0].detail


@pytest.mark.parametrize("cur", ["usd", " USD ", "Usd"])
def test_currency_is_compared_case_and_space_insensitively(cur):  # still domestic: $75 cap
    assert ("A", "MEAL-01") in fired(run(rcp("A", ("food_beverage", 75.01), currency=cur)))


def test_refund_line_is_not_special():  # Limit: a negative line simply lowers the day's spend
    assert fired(run(rcp("A", ("food_beverage", 90.0), ("food_beverage", -20.0)))) == {}
