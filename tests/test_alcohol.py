import pytest

from validator.check import verdict
from validator.rules.alcohol import alcohol_checks
from validator.rules.merchant import merchant_checks

from conftest import RECEIPTS, fired, status, suffix_cats


def receipt(mcc="5812", kind="Client Entertainment", attendees=4, entity="GLOBAL", alcohol_usd=68.0):
    return {
        "mcc": mcc, "entity": entity, "submitted_expense_type": kind, "attendee_count": attendees,
        "line_items": [
            {"line_id": "R-L1", "amount_usd": 100.0},
            {"line_id": "R-L2", "amount_usd": alcohol_usd},
            {"line_id": "R-L3", "amount_usd": 20.0},
        ],
    }


CATS = {"R-L1": "food_beverage", "R-L2": "alcohol", "R-L3": "service_fee"}


def test_one_check_per_rule_in_fixed_order():
    assert [c.rule_id for c in alcohol_checks(receipt(), CATS)] == ["ALC-01", "ALC-02", "ALC-03", "REG-01"]


def test_no_alcohol_means_nothing_applies():
    cats = {**CATS, "R-L2": "food_beverage"}
    assert set(status(alcohol_checks(receipt(kind="Meals - Individual", attendees=None), cats)).values()) == {"not_applicable"}


# --- ALC-01: alcohol needs Client Entertainment with 2+ attendees -------------------------------

def test_alc01_individual_meal_fires():  # RCP-010
    assert fired(alcohol_checks(receipt(kind="Meals - Individual", attendees=None), CATS)) == {"ALC-01": ("high", ("R-L2",))}


def test_alc01_team_meal_fires_even_with_attendees():
    assert "ALC-01" in fired(alcohol_checks(receipt(kind="Meals - Team", attendees=4), CATS))


@pytest.mark.parametrize("attendees, expected", [(None, True), (1, True), (2, False), (3, False)])
def test_alc01_attendee_boundary(attendees, expected):
    assert ("ALC-01" in fired(alcohol_checks(receipt(attendees=attendees), CATS))) is expected


# --- ALC-02: $30 per attendee, strictly above ----------------------------------------------------

@pytest.mark.parametrize("alcohol_usd, expected", [(119.99, False), (120.00, False), (120.01, True)])
def test_alc02_boundary_with_four_attendees(alcohol_usd, expected):  # 4 x $30 = $120
    assert ("ALC-02" in fired(alcohol_checks(receipt(alcohol_usd=alcohol_usd), CATS))) is expected


def test_alc02_is_not_evaluated_when_alc01_already_fired():
    assert status(alcohol_checks(receipt(kind="Meals - Individual", attendees=None), CATS))["ALC-02"] == "not_applicable"


def test_alc02_fires_medium_and_cites_only_the_alcohol_line():  # RCP-015
    assert fired(alcohol_checks(receipt(attendees=2, alcohol_usd=110.0), CATS)) == {"ALC-02": ("medium", ("R-L2",))}


# --- ALC-03: retail alcohol, regardless of context ----------------------------------------------

def test_alc03_fires_for_a_liquor_store_even_with_client_entertainment_and_attendees():  # RCP-011
    checks = alcohol_checks(receipt(mcc="5921"), CATS)
    assert fired(checks) == {"ALC-03": ("high", ("R-L2",))}
    assert status(checks)["ALC-01"] == "not_applicable" and status(checks)["ALC-02"] == "not_applicable"


def test_alc03_fires_for_a_supermarket():  # RCP-014
    assert "ALC-03" in fired(alcohol_checks(receipt(mcc="5411", kind="Office Supplies", attendees=None), CATS))


@pytest.mark.parametrize("mcc", ["5812", "5813", "7011"])
def test_on_premises_mccs_are_never_retail(mcc):  # MCC-03: a bar (5813) is not retail
    assert "ALC-03" not in fired(alcohol_checks(receipt(mcc=mcc), CATS))


# --- REG-01: APAC override -----------------------------------------------------------------------

def test_reg01_replaces_the_global_rules_for_apac():  # RCP-016
    checks = alcohol_checks(receipt(entity="APAC", alcohol_usd=16.2, attendees=3), CATS)
    assert fired(checks) == {"REG-01": ("high", ("R-L2",))}
    assert {r: s for r, s in status(checks).items() if r != "REG-01"} == {"ALC-01": "superseded", "ALC-02": "superseded", "ALC-03": "superseded"}


def test_reg01_also_replaces_alc03_for_apac_retail():
    checks = alcohol_checks(receipt(entity="APAC", mcc="5921"), CATS)
    assert fired(checks) == {"REG-01": ("high", ("R-L2",))} and status(checks)["ALC-03"] == "superseded"


# --- Real receipts, with categories written by hand (the answer key is not read) -----------------

REAL = {
    "RCP-002": ({"L2": "alcohol"}, {}),
    "RCP-004": ({}, {}),
    "RCP-010": ({"L2": "alcohol"}, {"ALC-01": ("high", ("RCP-010-L2",))}),
    "RCP-011": ({"L1": "alcohol"}, {"ALC-03": ("high", ("RCP-011-L1",))}),
    "RCP-014": ({"L4": "alcohol"}, {"ALC-03": ("high", ("RCP-014-L4",))}),
    "RCP-015": ({"L2": "alcohol"}, {"ALC-02": ("medium", ("RCP-015-L2",))}),
    "RCP-016": ({"L2": "alcohol"}, {"REG-01": ("high", ("RCP-016-L2",))}),
    "RCP-025": ({"L2": "alcohol"}, {"ALC-01": ("high", ("RCP-025-L2",))}),
}


@pytest.mark.parametrize("rid", REAL)
def test_real_receipts(rid):
    r = RECEIPTS[rid]
    by_suffix, expected = REAL[rid]
    cats = suffix_cats(r, by_suffix)
    assert fired(alcohol_checks(r, cats)) == expected


def test_alc02_sums_every_alcohol_line():  # 2 x $70 = $140 > 4 x $30
    r = receipt()
    r["line_items"] = [{"line_id": "R-L1", "amount_usd": 70.0}, {"line_id": "R-L2", "amount_usd": 70.0}]
    checks = alcohol_checks(r, {"R-L1": "alcohol", "R-L2": "alcohol"})
    assert fired(checks) == {"ALC-02": ("medium", ("R-L1", "R-L2"))}


def test_emea_keeps_the_global_rules():
    assert fired(alcohol_checks(receipt(entity="EMEA", kind="Meals - Individual", attendees=None), CATS)) == {"ALC-01": ("high", ("R-L2",))}


def test_missing_category_fails_closed():
    with pytest.raises(KeyError):
        alcohol_checks(receipt(), {"R-L1": "food_beverage", "R-L3": "service_fee"})


@pytest.mark.parametrize("mcc", [5812, " 5812"])
def test_restaurant_mcc_that_is_not_an_exact_string_is_still_on_premises(mcc):
    assert "ALC-03" not in fired(alcohol_checks(receipt(mcc=mcc), CATS))


def test_apac_liquor_store_gets_reg01_and_mcc01_together():  # REG-01: merchant rules "still apply"
    r = receipt(entity="APAC", mcc="5921")
    checks = alcohol_checks(r, CATS) + merchant_checks(r)
    assert fired(checks) == {"REG-01": ("high", ("R-L2",)), "MCC-01": ("high", ())}
    assert verdict(checks) == "flag"  # no duplicate rule ids


@pytest.mark.parametrize("bad", [True, 2.5, 0, "4"])
def test_bad_attendee_count_raises(bad):
    with pytest.raises(ValueError):
        alcohol_checks(receipt(attendees=bad), CATS)
