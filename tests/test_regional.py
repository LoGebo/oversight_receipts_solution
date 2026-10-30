from decimal import Decimal

import pytest

from validator.check import verdict
from validator.loader import load_receipts
from validator.rules.regional import RULE_IDS, meal_per_person, regional_checks

from conftest import RECEIPTS, fired, status


def receipt(*lines, rid="R", kind="Meals - Individual", country="FR", entity="EMEA", currency="EUR", rate=1.08,
            attendees=None, itemized=True, total=None, when="2026-04-23T13:10:00", employee="E-1"):
    """lines: (category, amount_usd); line ids are <rid>-L1, ...; total (local) defaults to the USD sum / rate."""
    usd = sum(Decimal(str(a)) for _, a in lines)
    items = [{"line_id": f"{rid}-L{i}", "amount_usd": a} for i, (_, a) in enumerate(lines, 1)]
    r = {"receipt_id": rid, "employee_id": employee, "employee_country": country, "entity": entity,
         "submitted_expense_type": kind, "transaction_datetime": when, "currency": currency,
         "fx_rate_to_usd": rate, "total_amount": float(usd / Decimal(str(rate))) if total is None else total,
         "total_amount_usd": float(usd), "attendee_count": attendees, "itemized": itemized, "line_items": items}
    return r, {f"{rid}-L{i}": c for i, (c, _) in enumerate(lines, 1)}


def run(*lines, same_day=(), eur_usd=None, **kw):
    r, cats = receipt(*lines, **kw)
    for _, c in same_day:
        cats |= c
    return regional_checks(r, cats, [o for o, _ in same_day], eur_usd=eur_usd)


def test_one_check_per_rule_in_fixed_order():
    assert [c.rule_id for c in run(("food_beverage", 10.0))] == ["REG-03", "REG-04", "REG-05"]
    assert tuple(c.rule_id for c in run(("food_beverage", 10.0))) == RULE_IDS


# --- Which entity: EMEA only; APAC has REG-01/REG-02 instead ------------------------------------

@pytest.mark.parametrize("country, entity", [("US", "GLOBAL"), ("IN", "APAC"), ("JP", "APAC"), ("SG", "APAC")])
def test_reg03_reg04_do_not_apply_outside_emea(country, entity):
    checks = run(("food_beverage", 500.0), country=country, entity=entity, currency="USD", rate=1.0)
    assert status(checks) == {"REG-03": "not_applicable", "REG-04": "not_applicable", "REG-05": "not_fired"}


@pytest.mark.parametrize("country", ["GB", "DE", "FR", "NL", "IE", "PT", "ES"])
def test_every_emea_country_is_covered(country):
    assert fired(run(("food_beverage", 100.0), country=country)) == {"REG-03": ("medium", ()), "REG-04": ("low", ())}


@pytest.mark.parametrize("country, entity", [("US", "EMEA"), ("FR", "GLOBAL"), ("DE", "APAC"), ("JP", "GLOBAL")])
def test_entity_that_contradicts_the_country_is_an_error(country, entity):
    with pytest.raises(ValueError):
        run(("food_beverage", 10.0), country=country, entity=entity)


# --- REG-03: EUR 70 per person per day, at the receipt's euro rate -----------------------------

@pytest.mark.parametrize("usd, expected", [(75.59, False), (75.60, False), (75.61, True)])
def test_reg03_boundary_at_eur70_times_rate(usd, expected):  # 70 x 1.08 = $75.60
    assert ("REG-03" in fired(run(("food_beverage", usd)))) is expected


def test_reg03_uses_the_receipts_own_rate():  # 70 x 1.20 = $84
    assert "REG-03" not in fired(run(("food_beverage", 84.0), rate=1.20))
    assert "REG-03" in fired(run(("food_beverage", 84.01), rate=1.20))


def test_reg03_is_medium_citing_no_lines():
    assert fired(run(("food_beverage", 40.0), ("alcohol", 30.0), ("service_fee", 10.0)))["REG-03"] == ("medium", ())


@pytest.mark.parametrize("attendees, expected", [(None, True), (1, True), (2, False)])
def test_reg03_divides_by_attendees_or_one(attendees, expected):  # $100 total
    assert ("REG-03" in fired(run(("food_beverage", 100.0), attendees=attendees, kind="Meals - Team"))) is expected


def test_reg03_two_attendees_boundary():  # 2 x $75.60 = $151.20
    assert "REG-03" not in fired(run(("food_beverage", 151.20), attendees=2, kind="Meals - Team"))
    assert "REG-03" in fired(run(("food_beverage", 151.21), attendees=2, kind="Meals - Team"))


def test_reg03_only_food_drink_and_gratuity_count():
    lines = [("food_beverage", 50.0), ("gift", 45.0), ("other", 30.0)]
    assert "REG-03" not in fired(run(*lines, kind="Client Entertainment"))
    assert meal_per_person(*receipt(*lines, kind="Client Entertainment")) == Decimal("50.0")


@pytest.mark.parametrize("cat", ["alcohol", "service_fee"])
def test_reg03_alcohol_and_gratuity_are_meal_spend(cat):
    assert "REG-03" in fired(run(("food_beverage", 70.0), (cat, 5.61)))


@pytest.mark.parametrize("kind", ["Lodging", "Travel - Other", "Client Gifts", "Office Supplies"])
def test_reg03_not_a_meal_type(kind):
    assert status(run(("food_beverage", 500.0), kind=kind))["REG-03"] == "not_applicable"


def test_reg03_meal_type_without_food_or_drink_is_not_a_meal_receipt():
    assert status(run(("gift", 500.0), ("service_fee", 20.0), kind="Client Entertainment"))["REG-03"] == "not_applicable"


def test_reg03_non_itemized_meal_uses_the_full_total():
    checks = run(("other", 100.0), itemized=False, kind="Meals - Team", attendees=1)
    assert "REG-03" in fired(checks)


def test_reg03_adds_the_same_days_receipts():  # $40 + $40 = $80 > $75.60, neither alone
    other = receipt(("food_beverage", 40.0), rid="B", when="2026-04-23T19:00:00")
    assert "REG-03" not in fired(run(("food_beverage", 40.0)))
    assert "REG-03" in fired(run(("food_beverage", 40.0), same_day=[other]))


def test_reg03_same_day_non_meal_receipt_adds_nothing():
    other = receipt(("food_beverage", 40.0), rid="B", kind="Lodging")
    assert "REG-03" not in fired(run(("food_beverage", 40.0), same_day=[other]))


@pytest.mark.parametrize("bad", [dict(employee="E-2"), dict(when="2026-04-24T08:00:00"), dict(rid="R")])
def test_reg03_same_day_must_be_the_employees_other_receipts_that_day(bad):
    other = receipt(("food_beverage", 1.0), **{"rid": "B", **bad})
    with pytest.raises(ValueError):
        run(("food_beverage", 40.0), same_day=[other])


def test_reg03_non_eur_receipt_needs_the_euro_rate():  # no guessing: each rule needing it is its own ERR signal
    checks = run(("food_beverage", 80.0), currency="USD", rate=1.0)
    assert [(c.rule_id, c.status, c.kind) for c in checks] == [
        ("ERR-REG-03", "fired", "signal"), ("ERR-REG-04", "fired", "signal"), ("REG-05", "not_fired", "exception")]
    assert verdict(checks) == "review"
    assert "REG-03" not in fired(run(("food_beverage", 80.0), currency="USD", rate=1.0, eur_usd=1.15))  # cap $80.50
    assert "REG-03" in fired(run(("food_beverage", 80.0), currency="USD", rate=1.0, eur_usd=1.14))      # cap $79.80


@pytest.mark.parametrize("attendees", [0, -2, 2.0, "2", True])
def test_bad_attendee_count_is_an_error(attendees):
    with pytest.raises(ValueError):
        run(("food_beverage", 10.0), attendees=attendees)


def test_missing_category_fails_closed():
    r, _ = receipt(("food_beverage", 10.0))
    with pytest.raises(KeyError):
        regional_checks(r, {})


# --- REG-04: above EUR 50 needs a VAT number, which the record never holds ----------------------

@pytest.mark.parametrize("eur, expected", [(49.99, False), (50.00, False), (50.01, True)])
def test_reg04_boundary_on_the_eur_total(eur, expected):
    r, cats = receipt(("lodging", round(eur * 1.08, 2)), kind="Lodging", total=eur)
    assert ("REG-04" in fired(regional_checks(r, cats))) is expected


def test_reg04_is_low_citing_no_lines_and_alone_reviews():
    r, cats = receipt(("lodging", 64.8), kind="Lodging", total=60.0)
    checks = regional_checks(r, cats)
    assert fired(checks) == {"REG-04": ("low", ())} and verdict(checks) == "review"


def test_reg04_applies_to_any_expense_type():
    assert "REG-04" in fired(run(("software_subscription", 100.0), kind="Software"))


def test_reg04_non_eur_receipt_converts_at_the_euro_rate():  # $57.50 / 1.15 = EUR 50.00
    assert "REG-04" not in fired(run(("lodging", 57.50), kind="Lodging", currency="USD", rate=1.0, eur_usd=1.15))
    assert "REG-04" in fired(run(("lodging", 57.51), kind="Lodging", currency="USD", rate=1.0, eur_usd=1.15))
    checks = run(("lodging", 57.51), kind="Lodging", currency="USD", rate=1.0)  # no euro rate: REG-04 alone is lost
    assert status(checks) == {"REG-03": "not_applicable", "ERR-REG-04": "fired", "REG-05": "not_fired"}


@pytest.mark.parametrize("eur_usd", [0, -1.1, "1.1", True])
def test_bad_euro_rate_is_an_error(eur_usd):
    with pytest.raises(ValueError):
        run(("lodging", 60.0), kind="Lodging", currency="USD", rate=1.0, eur_usd=eur_usd)


# --- REG-05: raises nothing on its own; a missing rate is DOC-04's ------------------------------

def test_reg05_never_fires():
    r, cats = receipt(("food_beverage", 10.0))
    r["fx_rate_to_usd"] = None
    assert status(regional_checks(r, cats, eur_usd=1.08))["REG-05"] == "not_fired"  # missing rate: DOC-04 reports it
    r, cats = receipt(("food_beverage", 10.0), country="US", entity="GLOBAL", currency="EUR", rate=1.08, total=10.0)
    assert status(regional_checks(r, cats))["REG-05"] == "not_fired"  # USD total off the rate: the engine's ERR-input


# --- Real receipts, with categories written by hand (the answer key is not read) -----------------

F, A, S = "food_beverage", "alcohol", "service_fee"
EMEA = {  # every EMEA receipt in the input; all are EUR
    "RCP-008": [F, F, F],          # Meals - Team, 2 attendees: $49.68 / 2 = $24.84 vs $75.60; EUR 46
    "RCP-025": [F, A, F],          # Meals - Individual: $37.80 vs $75.60; EUR 35
    "RCP-031": ["laundry_service"],  # Travel - Other: not a meal receipt; EUR 20
}


@pytest.mark.parametrize("rid, reg03", [("RCP-008", "not_fired"), ("RCP-025", "not_fired"), ("RCP-031", "not_applicable")])
def test_real_emea_receipts(rid, reg03):
    r = RECEIPTS[rid]
    cats = {li["line_id"]: c for li, c in zip(r["line_items"], EMEA[rid], strict=True)}
    assert status(regional_checks(r, cats)) == {"REG-03": reg03, "REG-04": "not_fired", "REG-05": "not_fired"}


def test_real_receipt_per_person_spend():
    r = RECEIPTS["RCP-008"]
    assert meal_per_person(r, {li["line_id"]: F for li in r["line_items"]}) == Decimal("24.84")


def test_real_non_emea_receipts_fire_nothing_and_are_consistent():  # also checks every USD total vs its rate
    emea = [r for r in load_receipts() if r["entity"] == "EMEA"]
    assert sorted(r["receipt_id"] for r in emea) == sorted(EMEA)
    for r in load_receipts():
        if r["entity"] != "EMEA":
            checks = regional_checks(r, {li["line_id"]: "other" for li in r["line_items"]})
            assert status(checks) == {"REG-03": "not_applicable", "REG-04": "not_applicable", "REG-05": "not_fired"}


# --- Exact arithmetic, grouping and currency normalisation ---------------------------------------

@pytest.mark.parametrize("third, expected", [(126.80, False), (126.81, True)])
def test_reg03_exactly_at_cap_in_thirds_does_not_fire(third, expected):  # (50 + 50 + 126.80) / 3 = $75.60
    same = [receipt(("food_beverage", usd), rid=x, kind="Meals - Team", attendees=3, when="2026-04-23T19:00:00")
            for x, usd in (("B", 50.0), ("C", 50.0))]
    assert ("REG-03" in fired(run(("food_beverage", third), kind="Meals - Team", attendees=3, same_day=same))) is expected


def test_reg03_receipt_without_employee_is_never_pooled():
    other = receipt(("food_beverage", 40.0), rid="B", employee=None)
    with pytest.raises(ValueError):
        run(("food_beverage", 40.0), employee=None, same_day=[other])


@pytest.mark.parametrize("cur", ["eur", " EUR "])
def test_eur_is_recognised_case_and_space_insensitively(cur):  # its own rate, no eur_usd needed
    assert fired(run(("food_beverage", 75.61), currency=cur)) == {"REG-03": ("medium", ()), "REG-04": ("low", ())}
