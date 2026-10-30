import pytest

from validator.loader import load_receipts
from validator.rules.health import health_checks


def rcp(rid, trip, *lines):
    """lines: (category, amount_usd); line ids are <rid>-L1, <rid>-L2, ..."""
    items = [{"line_id": f"{rid}-L{i}", "amount_usd": ln[1]} for i, ln in enumerate(lines, 1)]
    return {"receipt_id": rid, "trip_id": trip, "line_items": items}, {f"{rid}-L{i}": ln[0] for i, ln in enumerate(lines, 1)}


def run(*receipts):
    rs, cats = [r for r, _ in receipts], {k: v for _, c in receipts for k, v in c.items()}
    return health_checks(rs, cats)


def fired(result):
    return {rid: (c.severity, c.line_ids) for rid, c in result.items() if c.status == "fired"}


def status(result):
    return {rid: c.status for rid, c in result.items()}


def test_one_health01_check_per_receipt():
    out = run(rcp("A", "T1", ("health_otc", 5.0)), rcp("B", None, ("food_beverage", 5.0)), rcp("C", "T1"))
    assert list(out) == ["A", "B", "C"] and {c.rule_id for c in out.values()} == {"HEALTH-01"}
    assert status(out) == {"A": "not_fired", "B": "not_applicable", "C": "not_applicable"}


def test_missing_category_fails_closed():
    with pytest.raises(KeyError):
        health_checks([{"receipt_id": "A", "trip_id": "T1", "line_items": [{"line_id": "A-L1", "amount_usd": 1.0}]}], {})


def test_no_trip_fires_even_at_one_dollar():
    assert fired(run(rcp("A", None, ("health_otc", 1.0), ("food_beverage", 3.0)))) == {"A": ("low", ("A-L1",))}


def test_missing_trip_id_key_fires():
    out = health_checks([{"receipt_id": "A", "line_items": [{"line_id": "A-L1", "amount_usd": 1.0}]}], {"A-L1": "health_otc"})
    assert fired(out) == {"A": ("low", ("A-L1",))}


@pytest.mark.parametrize("usd, expected", [(24.99, False), (25.00, False), (25.01, True)])
def test_single_receipt_boundary(usd, expected):
    assert fired(run(rcp("A", "T1", ("health_otc", usd)))) == ({"A": ("low", ("A-L1",))} if expected else {})


def test_lines_on_one_receipt_are_summed():  # $13 + $12.01 = $25.01
    out = run(rcp("A", "T1", ("health_otc", 13.0), ("food_beverage", 50.0), ("health_otc", 12.01)))
    assert fired(out) == {"A": ("low", ("A-L1", "A-L3"))}


# --- Across the trip's receipts ------------------------------------------------------------------

def test_trip_total_over_cap_fires_on_each_receipt_citing_its_own_lines():  # $15 + $15 = $30
    out = run(rcp("A", "T1", ("health_otc", 15.0), ("food_beverage", 4.0)), rcp("B", "T1", ("food_beverage", 2.0), ("health_otc", 15.0)))
    assert fired(out) == {"A": ("low", ("A-L1",)), "B": ("low", ("B-L2",))}
    assert "$30" in out["A"].detail and "$25" in out["A"].detail


@pytest.mark.parametrize("second, expected", [(10.0, False), (10.01, True)])
def test_trip_total_boundary(second, expected):  # $15 + $10 = $25 passes
    out = run(rcp("A", "T1", ("health_otc", 15.0)), rcp("B", "T1", ("health_otc", second)))
    assert set(fired(out)) == ({"A", "B"} if expected else set())


def test_trip_receipt_without_medication_is_not_applicable():
    out = run(rcp("A", "T1", ("health_otc", 30.0)), rcp("B", "T1", ("food_beverage", 30.0)))
    assert status(out) == {"A": "fired", "B": "not_applicable"}


def test_unrelated_trip_is_not_mixed_in():  # $15 on T1, $15 on T2: each under $25
    out = run(rcp("A", "T1", ("health_otc", 15.0)), rcp("B", "T2", ("health_otc", 15.0)))
    assert status(out) == {"A": "not_fired", "B": "not_fired"}


def test_tripless_receipts_are_not_pooled_into_a_trip():  # None is not a trip id
    out = run(rcp("A", "T1", ("health_otc", 15.0)), rcp("B", None, ("health_otc", 15.0)), rcp("C", None, ("health_otc", 15.0)))
    assert status(out) == {"A": "not_fired", "B": "fired", "C": "fired"}


def test_other_categories_never_count_toward_the_cap():
    out = run(rcp("A", "T1", ("health_otc", 20.0), ("other", 100.0)), rcp("B", "T1", ("personal_care", 50.0)))
    assert status(out) == {"A": "not_fired", "B": "not_applicable"}


# --- Real receipts, with categories written by hand (the answer key is not read) -----------------

def test_rcp028_otc_on_its_trip_under_cap():  # ibuprofen $8.99 + lozenges $5.49 = $14.48 on TRIP-0248
    rs = load_receipts()
    cats = {li["line_id"]: "other" for r in rs for li in r["line_items"]}
    cats.update({"RCP-028-L1": "health_otc", "RCP-028-L2": "health_otc"})
    out = health_checks(rs, cats)
    assert len(out) == len(rs) and fired(out) == {}
    assert out["RCP-028"].status == "not_fired" and "$14.48" in out["RCP-028"].detail


# --- Prescription medication: never reimbursable, medium (non-reimbursable-items.md) -------------

@pytest.mark.parametrize("trip", ["T1", None])
def test_prescription_fires_medium_at_any_amount_trip_or_not(trip):
    out = run(rcp("A", trip, ("food_beverage", 3.0), ("prescription_medication", 1.0)))
    assert fired(out) == {"A": ("medium", ("A-L2",))}


def test_otc_alone_stays_low():
    assert fired(run(rcp("A", None, ("health_otc", 5.0)))) == {"A": ("low", ("A-L1",))}


def test_prescription_with_otc_under_the_cap_cites_only_the_prescription():  # OTC $10 on a trip is reimbursable
    out = run(rcp("A", "T1", ("health_otc", 10.0), ("prescription_medication", 40.0)))
    assert fired(out) == {"A": ("medium", ("A-L2",))}


def test_prescription_with_otc_over_the_cap_is_one_medium_check_citing_both():  # OTC $26 > $25
    out = run(rcp("A", "T1", ("prescription_medication", 40.0), ("health_otc", 26.0)))
    assert fired(out) == {"A": ("medium", ("A-L1", "A-L2"))} and "$26" in out["A"].detail


def test_prescription_never_counts_toward_the_otc_cap():  # $20 OTC + $100 prescription on the trip: OTC under cap
    out = run(rcp("A", "T1", ("health_otc", 20.0)), rcp("B", "T1", ("prescription_medication", 100.0)))
    assert status(out) == {"A": "not_fired", "B": "fired"} and fired(out) == {"B": ("medium", ("B-L1",))}
