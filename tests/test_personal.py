import pytest

from validator.check import verdict
from validator.loader import load_receipts
from validator.rules import personal
from validator.rules.personal import RULE_IDS, personal_checks

from conftest import RECEIPTS, fired, status, suffix_cats

BAG = "BAG-2026-0001"  # stands in for a baggage-delay reference; ref_kind recognises none today


@pytest.fixture
def baggage(monkeypatch):
    monkeypatch.setattr(personal, "ref_kind", lambda ref: "baggage_delay" if ref == BAG else None)


def run(*lines, ref=None):
    """lines: (category, amount_usd); line ids are R-L1, R-L2, ..."""
    items = [{"line_id": f"R-L{i}", "amount_usd": ln[1], "quantity": 1} for i, ln in enumerate(lines, 1)]
    cats = {f"R-L{i}": ln[0] for i, ln in enumerate(lines, 1)}
    return personal_checks({"line_items": items, "pre_approval_ref": ref}, cats)


def test_one_check_per_rule_in_fixed_order():
    assert [c.rule_id for c in run(("food_beverage", 10.0))] == ["PERS-01", "PERS-02"]
    assert tuple(c.rule_id for c in run()) == RULE_IDS


def test_ordinary_lines_mean_nothing_applies():
    assert status(run(("food_beverage", 10.0), ("laundry_service", 20.0))) == {
        "PERS-01": "not_applicable", "PERS-02": "not_applicable"}


def test_missing_category_fails_closed():
    with pytest.raises(KeyError):
        personal_checks({"line_items": [{"line_id": "R-L1", "amount_usd": 1.0}]}, {})


# --- Without a baggage-delay reference: each rule cites its own lines -----------------------------

def test_no_ref_each_rule_cites_only_its_own_lines():
    checks = run(("personal_care", 100.0), ("food_beverage", 5.0), ("clothing", 60.0), ("personal_care", 3.0))
    assert fired(checks) == {"PERS-01": ("medium", ("R-L1", "R-L4")), "PERS-02": ("medium", ("R-L3",))}
    assert verdict(checks) == "flag"


@pytest.mark.parametrize("category, rule", [("personal_care", "PERS-01"), ("clothing", "PERS-02")])
def test_small_amount_still_fires_without_ref(category, rule):  # the $150 is only a carve-out
    checks = run((category, 1.0))
    assert fired(checks) == {rule: ("medium", ("R-L1",))}
    other = next(r for r in RULE_IDS if r != rule)
    assert status(checks)[other] == "not_applicable"


@pytest.mark.parametrize("ref", ["PA-2026-0412", "MGR-7", "", None])
def test_pre_approval_or_unknown_ref_does_not_waive(ref):  # EXC-02: needs a baggage-delay reference
    checks = run(("personal_care", 10.0), ("clothing", 10.0), ref=ref)
    assert fired(checks) == {"PERS-01": ("medium", ("R-L1",)), "PERS-02": ("medium", ("R-L2",))}


def test_real_ref_kind_has_no_baggage_delay_kind():  # premise: the carve-out is unreachable in the data
    assert all(personal.ref_kind(r["pre_approval_ref"]) != "baggage_delay" for r in load_receipts())


# --- With a baggage-delay reference: one $150 allowance shared by both categories -----------------

@pytest.mark.parametrize("care, clothes, expected", [(90.0, 60.0, False), (89.99, 60.0, False),
                                                     (90.01, 60.0, True), (100.0, 60.0, True)])
@pytest.mark.usefixtures("baggage")
def test_shared_allowance_boundary(care, clothes, expected):  # $150.00 passes, $150.01 fires
    checks = run(("personal_care", care), ("clothing", clothes), ref=BAG)
    if expected:
        assert fired(checks) == {"PERS-01": ("medium", ("R-L1", "R-L2")), "PERS-02": ("medium", ("R-L1", "R-L2"))}
    else:
        assert status(checks) == {"PERS-01": "not_fired", "PERS-02": "not_fired"}


@pytest.mark.usefixtures("baggage")
def test_allowance_is_shared_not_per_category():  # $100 + $100: each under $150, together over
    assert set(fired(run(("personal_care", 100.0), ("clothing", 100.0), ref=BAG))) == {"PERS-01", "PERS-02"}


@pytest.mark.parametrize("category, rule", [("personal_care", "PERS-01"), ("clothing", "PERS-02")])
@pytest.mark.parametrize("usd, expected", [(150.0, False), (150.01, True)])
@pytest.mark.usefixtures("baggage")
def test_single_category_boundary(category, rule, usd, expected):
    checks = run((category, usd), ("food_beverage", 500.0), ref=BAG)  # other categories never count
    assert fired(checks) == ({rule: ("medium", ("R-L1",))} if expected else {})
    assert status(checks)[next(r for r in RULE_IDS if r != rule)] == "not_applicable"


@pytest.mark.usefixtures("baggage")
def test_over_allowance_cites_every_involved_line_not_others():
    checks = run(("clothing", 80.0), ("food_beverage", 9.0), ("personal_care", 40.0), ("clothing", 31.0), ref=BAG)
    involved = ("R-L1", "R-L3", "R-L4")
    assert fired(checks) == {"PERS-01": ("medium", involved), "PERS-02": ("medium", involved)}


@pytest.mark.usefixtures("baggage")
def test_under_allowance_passes():
    checks = run(("personal_care", 20.0), ("clothing", 30.0), ref=BAG)
    assert fired(checks) == {} and verdict(checks) == "pass"
    assert "$50" in checks[0].detail and "$150" in checks[0].detail


# --- Real receipts, with categories written by hand (the answer key is not read) -----------------

REAL = {  # receipt -> ({line suffix: category}, expected fired)
    "RCP-027": ({"L1": "clothing", "L2": "clothing"},
                {"PERS-02": ("medium", ("RCP-027-L1", "RCP-027-L2"))}),  # dress shirt $68 + socks $18
    "RCP-009": ({"L1": "laundry_service"}, {}),  # dry cleaning is LAUNDRY-01, not PERS
    "RCP-031": ({"L1": "laundry_service"}, {}),
}


@pytest.mark.parametrize("rid", REAL)
def test_real_receipts(rid):
    r = RECEIPTS[rid]
    by_suffix, expected = REAL[rid]
    cats = suffix_cats(r, by_suffix)
    assert fired(personal_checks(r, cats)) == expected
