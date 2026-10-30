import pytest

from validator.check import verdict
from validator.loader import load_receipts
from validator.rules.lines import RULE_IDS, line_checks, ref_kind

from conftest import RECEIPTS, fired, status, suffix_cats


def run(*lines, ref=None, nights=None, trip="TRIP-1"):
    """lines: (category, amount_usd[, quantity]); line ids are R-L1, R-L2, ..."""
    items = [{"line_id": f"R-L{i}", "amount_usd": ln[1], "quantity": ln[2] if len(ln) > 2 else 1}
             for i, ln in enumerate(lines, 1)]
    cats = {f"R-L{i}": ln[0] for i, ln in enumerate(lines, 1)}
    return line_checks({"line_items": items, "pre_approval_ref": ref, "trip_id": trip, "trip_nights": nights}, cats)


def test_one_check_per_rule_in_fixed_order():
    assert [c.rule_id for c in run(("food_beverage", 10.0))] == [
        "TECH-01", "TECH-02", "TECH-03", "TECH-04", "ENT-01", "ENT-02", "PERS-03", "HOUSE-01", "LAUNDRY-01"]
    assert tuple(c.rule_id for c in run()) == RULE_IDS


def test_ordinary_lines_mean_nothing_applies():
    assert set(status(run(("food_beverage", 10.0), ("office_supplies", 5.0))).values()) == {"not_applicable"}


def test_missing_category_fails_closed():
    r = {"line_items": [{"line_id": "R-L1", "amount_usd": 1.0, "quantity": 1}]}
    with pytest.raises(KeyError):
        line_checks(r, {})


# --- Category-only rules: severity copied from the policy, every line cited once -----------------

@pytest.mark.parametrize("category, rule, severity", [
    ("personal_electronics", "TECH-01", "high"),
    ("mobile_handset", "TECH-03", "high"),
    ("gambling", "ENT-02", "high"),
    ("tobacco", "PERS-03", "high"),
    ("household_goods", "HOUSE-01", "medium"),
    ("software_subscription", "TECH-04", "low"),
    ("entertainment_venue", "ENT-01", "medium"),
])
def test_category_rule_fires_once_citing_every_line(category, rule, severity):
    checks = run((category, 50.0), ("food_beverage", 5.0), (category, 7.0))
    assert fired(checks) == {rule: (severity, ("R-L1", "R-L3"))}


def test_two_rules_on_one_receipt_fire_independently():
    checks = run(("tobacco", 12.0), ("household_goods", 4.0))
    assert fired(checks) == {"PERS-03": ("high", ("R-L1",)), "HOUSE-01": ("medium", ("R-L2",))}
    assert verdict(checks) == "flag"


def test_tech01_ignores_any_reference():  # "regardless of stated business purpose"
    assert fired(run(("personal_electronics", 50.0), ref="PA-2026-0001")) == {"TECH-01": ("high", ("R-L1",))}


# --- EXC-02: only the kind of reference the rule asks for ----------------------------------------

@pytest.mark.parametrize("ref, kind", [("PA-2026-0412", "pre_approval"), (None, None), ("", None),
                                       ("pa-2026-0412", None), ("X-PA-1", None), (412, None),
                                       ("PO-2026-0412", None), ("PAX-2026-0412", None)])
def test_ref_kind(ref, kind):
    assert ref_kind(ref) == kind


def test_tech04_is_not_satisfied_by_a_pre_approval():  # needs a manager approval
    checks = run(("software_subscription", 144.0), ref="PA-2026-0001")
    assert fired(checks) == {"TECH-04": ("low", ("R-L1",))} and verdict(checks) == "review"


def test_ent01_is_not_satisfied_by_a_pre_approval():  # needs a VP approval
    assert fired(run(("entertainment_venue", 300.0), ref="PA-2026-0001")) == {"ENT-01": ("medium", ("R-L1",))}


# --- TECH-02: $200 per item, on the USD unit price, strictly above ------------------------------

@pytest.mark.parametrize("usd, expected", [(199.99, False), (200.00, False), (200.01, True)])
def test_tech02_boundary(usd, expected):
    assert ("TECH-02" in fired(run(("computer_accessory", usd)))) is expected


def test_tech02_is_per_item_not_per_line_total():  # 2 x $150: unit $150 passes though the line is $300
    checks = run(("computer_accessory", 300.0, 2))
    assert status(checks)["TECH-02"] == "not_fired"


def test_tech02_unit_price_above_cap_with_quantity():  # 2 x $200.01
    assert fired(run(("computer_accessory", 400.02, 2))) == {"TECH-02": ("medium", ("R-L1",))}


def test_tech02_does_not_add_items_together():  # $150 + $150 is not one $300 item
    assert status(run(("computer_accessory", 150.0), ("computer_accessory", 150.0)))["TECH-02"] == "not_fired"


def test_tech02_cites_only_the_lines_above_the_cap():
    checks = run(("computer_accessory", 329.0), ("computer_accessory", 14.99), ("computer_accessory", 250.0))
    assert fired(checks) == {"TECH-02": ("medium", ("R-L1", "R-L3"))}


def test_tech02_satisfied_by_a_pre_approval():
    c = next(c for c in run(("computer_accessory", 329.0), ref="PA-2026-0001") if c.rule_id == "TECH-02")
    assert c.status == "not_fired" and "pre-approval" in c.detail


def test_tech02_not_satisfied_by_an_unknown_reference():
    assert "TECH-02" in fired(run(("computer_accessory", 329.0), ref="MGR-7"))


@pytest.mark.parametrize("q", [0, -1, 1.5, 0.0, "2", None, True, float("nan"), float("inf")])
def test_tech02_bad_quantity_raises(q):
    with pytest.raises(ValueError):
        run(("computer_accessory", 300.0, q))


@pytest.mark.parametrize("q, expected", [(1.0, True), (2.0, False), (2, False)])
def test_tech02_integral_float_quantity_is_a_count(q, expected):  # $300 / 2 = $150 per item
    assert ("TECH-02" in fired(run(("computer_accessory", 300.0, q)))) is expected


def test_tech02_uses_amount_usd_not_local_unit_price():  # JPY 89,800 is $601.66
    r = {"line_items": [{"line_id": "R-L1", "amount_usd": 150.0, "quantity": 1, "unit_price": 22000.0}]}
    assert status(line_checks(r, {"R-L1": "computer_accessory"}))["TECH-02"] == "not_fired"


# --- LAUNDRY-01: four or more nights on the receipt ---------------------------------------------

@pytest.mark.parametrize("nights, expected", [(None, True), (0, True), (3, True), (4, False), (5, False)])
def test_laundry_boundary(nights, expected):
    assert ("LAUNDRY-01" in fired(run(("laundry_service", 34.0), nights=nights))) is expected


def test_laundry_fires_low_citing_the_lines():
    assert fired(run(("laundry_service", 20.0), ("laundry_service", 5.0), nights=2)) == {"LAUNDRY-01": ("low", ("R-L1", "R-L2"))}


def test_laundry_missing_trip_nights_key_fires():
    r = {"line_items": [{"line_id": "R-L1", "amount_usd": 20.0, "quantity": 1}]}
    assert fired(line_checks(r, {"R-L1": "laundry_service"})) == {"LAUNDRY-01": ("low", ("R-L1",))}


@pytest.mark.parametrize("trip, nights", [(None, 5), ("TRIP-1", None), (None, None)])
def test_laundry_needs_a_trip_record_linked_trip_and_nights(trip, nights):  # as HEALTH-01: trip_id, and its length
    c = next(c for c in run(("laundry_service", 20.0), trip=trip, nights=nights) if c.rule_id == "LAUNDRY-01")
    assert (c.status, c.severity, c.detail) == ("fired", "low", "no trip record")


@pytest.mark.parametrize("nights", ["5", 4.0, True])
def test_laundry_non_int_nights_raises(nights):
    with pytest.raises(ValueError):
        run(("laundry_service", 20.0), nights=nights)


# --- Real receipts, with categories written by hand (the answer key is not read) -----------------

REAL = {  # receipt -> ({line suffix: category}, expected fired)
    "RCP-003": ({"L1": "computer_accessory"}, {}),  # adapter $19.99
    "RCP-006": ({"L1": "computer_accessory"}, {}),  # dock $189
    "RCP-009": ({"L1": "laundry_service"}, {}),  # dry cleaning, 5 nights
    "RCP-012": ({"L1": "personal_electronics"}, {"TECH-01": ("high", ("RCP-012-L1",))}),  # headphones
    "RCP-014": ({"L1": "household_goods", "L2": "household_goods", "L3": "household_goods", "L4": "alcohol"},
                {"HOUSE-01": ("medium", ("RCP-014-L1", "RCP-014-L2", "RCP-014-L3"))}),
    "RCP-019": ({"L1": "personal_electronics", "L2": "personal_electronics"},
                {"TECH-01": ("high", ("RCP-019-L1", "RCP-019-L2"))}),  # iPad + its case
    "RCP-024": ({"L1": "tobacco"}, {"PERS-03": ("high", ("RCP-024-L1",))}),
    "RCP-026": ({"L1": "computer_accessory", "L2": "computer_accessory"},
                {"TECH-02": ("medium", ("RCP-026-L1",))}),  # monitor $329, not the $14.99 cable
    "RCP-031": ({"L1": "laundry_service"}, {"LAUNDRY-01": ("low", ("RCP-031-L1",))}),  # 2 nights
    "RCP-032": ({"L1": "software_subscription"}, {"TECH-04": ("low", ("RCP-032-L1",))}),  # Figma
}


@pytest.mark.parametrize("rid", REAL)
def test_real_receipts(rid):
    r = RECEIPTS[rid]
    by_suffix, expected = REAL[rid]
    cats = suffix_cats(r, by_suffix)
    assert fired(line_checks(r, cats)) == expected


def test_no_real_receipt_has_a_ref_that_is_not_a_pre_approval():  # premise of EXC-02 handling
    refs = [r["pre_approval_ref"] for r in load_receipts() if r["pre_approval_ref"] is not None]
    assert refs and all(ref_kind(ref) == "pre_approval" for ref in refs)
