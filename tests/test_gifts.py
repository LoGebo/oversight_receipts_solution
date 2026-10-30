from decimal import Decimal

import pytest

from validator.check import verdict
from validator.loader import load_receipts
from validator.rules.gifts import RULE_IDS, gift_checks

from conftest import RECEIPTS, fired, status, suffix_cats


def run(*lines, kind="Client Gifts", ref=None, hook=None):
    """lines: (category, amount_usd); line ids are R-L1, R-L2, ...; hook: {line number: (kind, name)}."""
    items = [{"line_id": f"R-L{i}", "amount_usd": ln[1]} for i, ln in enumerate(lines, 1)]
    cats = {f"R-L{i}": ln[0] for i, ln in enumerate(lines, 1)}
    for_ = None if hook is None else {f"R-L{n}": v for n, v in hook.items()}
    return gift_checks({"submitted_expense_type": kind, "pre_approval_ref": ref, "line_items": items}, cats, for_)


CLIENT = ("client", "A. Moreau")
OFFICIAL = ("government_official", "R. Delgado")


def test_one_check_per_rule_in_fixed_order():
    assert [c.rule_id for c in run(("gift", 5.0))] == ["GIFT-01", "GIFT-02", "GIFT-03", "GIFT-04"]
    assert tuple(c.rule_id for c in run()) == RULE_IDS


def test_ordinary_receipt_means_nothing_applies():
    assert set(status(run(("food_beverage", 80.0), ("office_supplies", 30.0), kind="Office Supplies")).values()) == {"not_applicable"}


def test_missing_category_fails_closed():
    with pytest.raises(KeyError):
        gift_checks({"submitted_expense_type": "Client Gifts", "line_items": [{"line_id": "R-L1", "amount_usd": 1.0}]}, {})


@pytest.mark.parametrize("usd", ["60", None, True, [60]])
def test_bad_amount_raises(usd):
    with pytest.raises(ValueError):
        run(("gift", usd))


def test_bad_amount_raises_even_on_a_line_no_rule_uses():
    with pytest.raises(ValueError):
        run(("office_supplies", "5"), kind="Office Supplies")


@pytest.mark.parametrize("v", [("friend", None), "client", ("client",), ("client", 7), ["client", None], ("Client", None)])
def test_bad_hook_value_raises(v):
    with pytest.raises(ValueError):
        run(("gift", 5.0), hook={1: v})


def test_hook_naming_a_line_not_on_the_receipt_raises():
    with pytest.raises(ValueError):
        run(("gift", 5.0), hook={2: CLIENT})


def test_decimal_amount_is_accepted():
    assert fired(run(("gift", Decimal("50.01")), hook={1: CLIENT})) == {"GIFT-01": ("medium", ("R-L1",))}


# --- What counts as a gift ------------------------------------------------------------------------

def test_jewelry_for_a_named_client_is_a_gift_on_any_receipt_type():  # category and purpose are separate
    assert fired(run(("jewelry", 180.0), kind="Travel - Other", hook={1: CLIENT})) == {"GIFT-01": ("medium", ("R-L1",))}


def test_gift_category_naming_nobody_off_a_client_gifts_receipt_is_not_a_gift():
    assert status(run(("gift", 80.0), kind="Office Supplies"))["GIFT-01"] == "not_applicable"


def test_every_line_on_a_client_gifts_receipt_is_a_gift_whatever_its_category():
    assert fired(run(("jewelry", 12.0), ("office_supplies", 11.0))) == {"GIFT-01": ("medium", ("R-L1", "R-L2"))}


@pytest.mark.parametrize("category", ["food_beverage", "alcohol", "service_fee"])
def test_meal_items_naming_a_guest_are_not_gifts(category):  # meal rules govern them
    assert status(run((category, 90.0), kind="Client Entertainment", hook={1: CLIENT}))["GIFT-01"] == "not_applicable"


@pytest.mark.parametrize("category", ["food_beverage", "alcohol", "service_fee"])
def test_meal_items_on_a_client_gifts_receipt_are_not_gifts(category):
    assert status(run((category, 90.0)))["GIFT-01"] == "not_applicable"


def test_reference_waives_nothing():  # EXC-02: no gift rule asks for one
    checks = run(("gift_card", 25.0), ("gift", 75.0), ref="PA-2026-0001", hook={2: CLIENT})
    assert fired(checks) == {"GIFT-02": ("high", ("R-L1",)), "GIFT-01": ("medium", ("R-L2",))}


# --- GIFT-01: $50 per recipient per receipt, strictly above; unnamed at $10 or more ----------------

@pytest.mark.parametrize("usd, expected", [(49.99, False), (50.00, False), (50.01, True)])
def test_gift01_cap_boundary_for_a_named_client(usd, expected):
    assert fired(run(("gift", usd), hook={1: CLIENT})) == ({"GIFT-01": ("medium", ("R-L1",))} if expected else {})


@pytest.mark.parametrize("usd, expected", [(9.99, False), (10.00, True), (10.01, True)])
def test_gift01_unnamed_boundary(usd, expected):  # "$10 or more" is inclusive
    assert fired(run(("gift", usd))) == ({"GIFT-01": ("medium", ("R-L1",))} if expected else {})


def test_gift01_small_unnamed_card_passes():
    c = run(("gift", 4.99))[0]
    assert c.status == "not_fired" and "$4.99" in c.detail and "$50" in c.detail


def test_gift01_named_gift_of_ten_or_more_passes_under_the_cap():
    assert status(run(("gift", 30.0), hook={1: CLIENT}))["GIFT-01"] == "not_fired"


def test_gift01_named_client_with_no_name_still_needs_one():  # kind known, name not
    assert fired(run(("gift", 20.0), kind="Travel - Other", hook={1: ("client", None)})) == {"GIFT-01": ("medium", ("R-L1",))}


@pytest.mark.parametrize("name", ["", "   "])
def test_gift01_blank_name_is_unnamed(name):
    assert fired(run(("gift", 20.0), hook={1: ("client", name)})) == {"GIFT-01": ("medium", ("R-L1",))}


@pytest.mark.parametrize("second, expected", [(20.0, False), (20.01, True)])
def test_gift01_lines_for_the_same_recipient_are_summed(second, expected):  # $30 + $20 = $50 passes
    checks = run(("gift", 30.0), ("jewelry", second), hook={1: CLIENT, 2: CLIENT})
    assert fired(checks) == ({"GIFT-01": ("medium", ("R-L1", "R-L2"))} if expected else {})


def test_gift01_recipient_names_match_ignoring_case_and_spaces():
    checks = run(("gift", 30.0), ("gift", 30.0), hook={1: CLIENT, 2: ("client", " a. moreau ")})
    assert fired(checks) == {"GIFT-01": ("medium", ("R-L1", "R-L2"))}


def test_gift01_different_recipients_are_not_summed():
    checks = run(("gift", 40.0), ("gift", 40.0), hook={1: CLIENT, 2: ("client", "B. Okafor")})
    assert status(checks)["GIFT-01"] == "not_fired"


def test_gift01_unnamed_gifts_are_not_summed():  # $9 + $9: each under $10, each its own recipient
    assert status(run(("gift", 9.0), ("gift", 9.0)))["GIFT-01"] == "not_fired"


def test_gift01_many_small_unnamed_gifts_never_pool_into_the_cap():  # 6 x $9 = $54, each tested alone
    assert status(run(*[("gift", 9.0)] * 6))["GIFT-01"] == "not_fired"


def test_gift01_unnamed_gift_over_the_cap_is_cited_once():
    assert fired(run(("gift", 60.0))) == {"GIFT-01": ("medium", ("R-L1",))}


def test_gift01_both_parts_in_one_exception_citing_only_the_lines_involved():
    checks = run(("gift", 30.0), ("gift", 4.0), ("jewelry", 25.0), ("gift", 12.0), hook={1: CLIENT, 3: CLIENT})
    assert fired(checks) == {"GIFT-01": ("medium", ("R-L1", "R-L3", "R-L4"))}


def test_gift01_skips_gift_cards():  # GIFT-02 alone
    checks = run(("gift_card", 100.0), hook={1: CLIENT})
    assert fired(checks) == {"GIFT-02": ("high", ("R-L1",))} and status(checks)["GIFT-01"] == "not_applicable"


def test_gift01_card_does_not_count_toward_the_recipients_cap():  # $45 gift + $100 card, same client
    checks = run(("gift", 45.0), ("gift_card", 100.0), hook={1: CLIENT, 2: CLIENT})
    assert fired(checks) == {"GIFT-02": ("high", ("R-L2",))} and status(checks)["GIFT-01"] == "not_fired"


# --- GIFT-02: gift cards never, at any amount, for anyone ----------------------------------------

@pytest.mark.parametrize("usd", [0.01, 5.0, 500.0])
def test_gift02_any_amount(usd):
    assert fired(run(("gift_card", usd))) == {"GIFT-02": ("high", ("R-L1",))}


def test_gift02_even_off_a_gift_receipt_naming_nobody():
    assert fired(run(("gift_card", 25.0), ("food_beverage", 8.0), kind="Office Supplies")) == {"GIFT-02": ("high", ("R-L1",))}


def test_gift02_cites_every_card_once():
    assert fired(run(("gift_card", 25.0), ("gift", 4.0), ("gift_card", 50.0)))["GIFT-02"] == ("high", ("R-L1", "R-L3"))


# --- GIFT-03: employee gifts go through HR --------------------------------------------------------

def test_gift03_employee_gift_any_amount():
    checks = run(("gift", 5.0), kind="Travel - Other", hook={1: ("employee", "J. Park")})
    assert fired(checks) == {"GIFT-03": ("medium", ("R-L1",))} and status(checks)["GIFT-01"] == "not_applicable"


def test_gift03_on_a_client_gifts_receipt_leaves_the_client_lines_to_gift01():
    checks = run(("gift", 80.0), ("jewelry", 30.0), hook={1: ("employee", "J. Park"), 2: CLIENT})
    assert fired(checks) == {"GIFT-03": ("medium", ("R-L1",))} and status(checks)["GIFT-01"] == "not_fired"


def test_gift03_employee_gift_card_is_gift02_alone():
    assert fired(run(("gift_card", 50.0), hook={1: ("employee", "J. Park")})) == {"GIFT-02": ("high", ("R-L1",))}


def test_gift03_team_meal_is_not_an_employee_gift():
    assert fired(run(("food_beverage", 90.0), kind="Meals - Team", hook={1: ("employee", "J. Park")})) == {}


# --- GIFT-04: government officials, any amount, meals included, never the gratuity -----------------

def test_gift04_covers_meals_and_gifts_but_not_the_gratuity():
    checks = run(("food_beverage", 68.0), ("gift", 45.0), ("service_fee", 15.0), ("alcohol", 20.0),
                 kind="Client Entertainment", hook={1: OFFICIAL, 2: OFFICIAL, 3: OFFICIAL, 4: OFFICIAL})
    assert fired(checks) == {"GIFT-04": ("critical", ("R-L1", "R-L2", "R-L4"))}
    assert status(checks)["GIFT-01"] == "superseded" and verdict(checks) == "flag"


def test_gift04_at_one_cent():
    assert fired(run(("gift", 0.01), hook={1: OFFICIAL})) == {"GIFT-04": ("critical", ("R-L1",))}


def test_gift04_replaces_gift01_only_for_the_officials_lines():
    checks = run(("gift", 60.0), ("gift", 60.0), hook={1: OFFICIAL, 2: CLIENT})
    assert fired(checks) == {"GIFT-04": ("critical", ("R-L1",)), "GIFT-01": ("medium", ("R-L2",))}


def test_gift04_officials_spend_never_counts_toward_a_clients_cap():  # same name, different kind
    checks = run(("gift", 30.0), ("gift", 30.0), hook={1: ("government_official", "A. Moreau"), 2: CLIENT})
    assert status(checks)["GIFT-01"] == "not_fired"


def test_gift04_official_meal_alone_does_not_supersede_gift01():  # no gift line was replaced
    checks = run(("food_beverage", 40.0), kind="Client Entertainment", hook={1: OFFICIAL})
    assert status(checks)["GIFT-01"] == "not_applicable"


def test_gift04_gift_card_to_an_official_raises_both():
    assert fired(run(("gift_card", 20.0), hook={1: OFFICIAL})) == {
        "GIFT-02": ("high", ("R-L1",)), "GIFT-04": ("critical", ("R-L1",))}


def test_gift04_without_the_hook_is_not_applicable_and_says_why():
    c = run(("gift", 45.0), kind="Client Entertainment")[3]
    assert c.status == "not_applicable" and "hook" in c.detail


# --- Real receipts, with categories and recipients written by hand (the answer key is not read) -----

REAL = {  # receipt -> ({line suffix: category}, {line suffix: (kind, name)}, expected fired)
    "RCP-002": ({"L1": "food_beverage", "L2": "alcohol", "L3": "service_fee"}, {}, {}),
    "RCP-013": ({"L1": "gift_card", "L2": "gift"}, {},
                {"GIFT-02": ("high", ("RCP-013-L1",))}),  # $100 Amazon card; $4.99 greeting card needs no name
    "RCP-018": ({"L1": "jewelry"}, {"L1": ("client", "A. Moreau")},
                {"GIFT-01": ("medium", ("RCP-018-L1",))}),  # $180 bracelet for one client > $50
    "RCP-022": ({"L1": "food_beverage", "L2": "gift"},
                {"L1": ("government_official", "R. Delgado"), "L2": ("government_official", "R. Delgado")},
                {"GIFT-04": ("critical", ("RCP-022-L1", "RCP-022-L2"))}),  # City Procurement Office
    "RCP-027": ({"L1": "clothing", "L2": "clothing"}, {}, {}),
}


@pytest.mark.parametrize("rid", REAL)
def test_real_receipts(rid):
    r = RECEIPTS[rid]
    by_suffix, hook, expected = REAL[rid]
    cats = suffix_cats(r, by_suffix)
    for_ = {f"{rid}-{s}": v for s, v in hook.items()}
    assert fired(gift_checks(r, cats, for_)) == expected


def test_rcp018_fires_without_the_hook_too():  # declared Client Gifts, $180 unnamed: both parts, one line
    r = RECEIPTS["RCP-018"]
    assert fired(gift_checks(r, {"RCP-018-L1": "jewelry"})) == {"GIFT-01": ("medium", ("RCP-018-L1",))}


def test_rcp022_without_the_hook_raises_nothing():  # documented limit: recipient is only in free text
    r = RECEIPTS["RCP-022"]
    assert fired(gift_checks(r, {"RCP-022-L1": "food_beverage", "RCP-022-L2": "gift"})) == {}


def test_every_real_receipt_runs_with_no_hook():
    for r in load_receipts():
        checks = gift_checks(r, {li["line_id"]: "other" for li in r["line_items"]})
        assert tuple(c.rule_id for c in checks) == RULE_IDS
