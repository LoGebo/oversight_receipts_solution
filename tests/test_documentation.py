from decimal import Decimal

import pytest

from validator.check import verdict
from validator.loader import load_receipts
from validator.rules.documentation import COVERS, RULE_IDS, documentation_checks

from conftest import RECEIPTS, fired, status


def receipt(*cats, kind="Meals - Individual", total=50.0, usd=None, itemized=True, currency="USD", rate=1.0,
            merchant="Cafe", when="2026-04-14T19:22:00"):
    """cats: one category per line; line ids are R-L1, R-L2, ..."""
    r = {"submitted_expense_type": kind, "merchant_name": merchant, "transaction_datetime": when,
         "currency": currency, "fx_rate_to_usd": rate, "total_amount": total,
         "total_amount_usd": total if usd is None else usd, "itemized": itemized,
         "line_items": [{"line_id": f"R-L{i}", "amount_usd": 1.0} for i in range(1, len(cats) + 1)]}
    return r, {f"R-L{i}": c for i, c in enumerate(cats, 1)}


def run(*cats, **kw):
    return documentation_checks(*receipt(*cats, **kw))


def test_one_check_per_rule_in_fixed_order():
    assert [c.rule_id for c in run("food_beverage")] == ["DOC-01", "DOC-02", "DOC-03", "DOC-04"]
    assert tuple(c.rule_id for c in run("food_beverage")) == RULE_IDS


def test_clean_receipt_fires_nothing():
    checks = run("food_beverage")
    assert fired(checks) == {} and verdict(checks) == "pass"


# --- DOC-01: non-itemized above $75 USD ---------------------------------------------------------

@pytest.mark.parametrize("usd, expected", [(74.99, False), (75.00, False), (75.01, True)])
def test_doc01_boundary(usd, expected):
    assert ("DOC-01" in fired(run("other", total=usd, itemized=False))) is expected


def test_doc01_never_fires_on_an_itemized_receipt():
    assert "DOC-01" not in fired(run("food_beverage", total=5000.0))


def test_doc01_is_medium_citing_no_lines_and_flags():
    checks = run("food_beverage", total=186.0, itemized=False)
    assert fired(checks) == {"DOC-01": ("medium", ())} and verdict(checks) == "flag"


def test_doc01_uses_the_usd_total_not_the_local_one():  # DOC-04: thresholds on the USD amount
    assert "DOC-01" not in fired(run("other", total=6000.0, usd=72.0, itemized=False, currency="INR", rate=0.012))
    assert "DOC-01" in fired(run("other", total=70.0, usd=75.6, itemized=False, currency="EUR", rate=1.08))


@pytest.mark.parametrize("itemized", [None, "false", 0, 1])
def test_itemized_must_be_a_bool(itemized):
    with pytest.raises(ValueError):
        run("other", itemized=itemized)


# --- DOC-02: merchant, date and total -----------------------------------------------------------

@pytest.mark.parametrize("field, value", [("merchant_name", None), ("merchant_name", "  "),
                                          ("transaction_datetime", None), ("transaction_datetime", ""),
                                          ("total_amount", None)])
def test_doc02_missing_field_fires_medium(field, value):
    r, cats = receipt("food_beverage")
    r[field] = value
    assert fired(documentation_checks(r, cats)) == {"DOC-02": ("medium", ())}


@pytest.mark.parametrize("field, value", [("merchant_name", 12), ("transaction_datetime", "yesterday"),
                                          ("total_amount", "48.20"), ("total_amount", True)])
def test_doc02_bad_types_are_errors_not_passes(field, value):
    r, cats = receipt("food_beverage")
    r[field] = value
    with pytest.raises(ValueError):
        documentation_checks(r, cats)


def test_doc02_lists_every_missing_field():
    c = run("food_beverage", merchant=None, when=None)[1]
    assert c.status == "fired" and "merchant name" in c.detail and "transaction date" in c.detail


def test_missing_total_does_not_crash_doc01():
    r, cats = receipt("other", itemized=False)
    r["total_amount"] = r["total_amount_usd"] = None
    assert status(documentation_checks(r, cats)) == {"DOC-01": "not_applicable", "DOC-02": "fired",
                                                     "DOC-03": "not_applicable", "DOC-04": "not_applicable"}


def test_missing_usd_total_alone_is_bad_data():
    r, cats = receipt("other")
    r["total_amount_usd"] = None
    with pytest.raises(ValueError):
        documentation_checks(r, cats)


# --- DOC-03: declared type vs contents ----------------------------------------------------------

@pytest.mark.parametrize("kind, cats", [
    ("Office Supplies", ["personal_electronics"]),             # RCP-012
    ("Office Supplies", ["household_goods", "alcohol"]),       # RCP-014
    ("Lodging", ["personal_care", "service_fee"]),             # RCP-017
    ("Software", ["computer_accessory"]),
    ("Meals - Team", ["gift"]),
])
def test_doc03_fires_when_no_line_is_covered(kind, cats):
    assert fired(run(*cats, kind=kind)) == {"DOC-03": ("medium", ())}


@pytest.mark.parametrize("kind, cats", [
    ("Client Entertainment", ["food_beverage", "gift"]),       # one covered line is enough (RCP-022)
    ("Meals - Individual", ["tobacco", "food_beverage"]),      # RCP-024
    ("Computer Equipment", ["personal_electronics"]),          # correctly declared, TECH-01 is separate
    ("Travel - Other", ["clothing"]),
])
def test_doc03_one_covered_line_passes(kind, cats):
    assert status(run(*cats, kind=kind))["DOC-03"] == "not_fired"


@pytest.mark.parametrize("cats", [["service_fee"], ["other"], ["service_fee", "other"], [],
                                  ["mobile_handset"], ["entertainment_venue"]])
def test_doc03_does_not_apply_when_only_ignored_lines_remain(cats):  # extensions map to `other`
    assert status(run(*cats, kind="Software"))["DOC-03"] == "not_applicable"


def test_doc03_ignored_lines_do_not_rescue_a_misclassification():
    assert "DOC-03" in fired(run("personal_care", "service_fee", "other", kind="Lodging"))


def test_doc03_non_itemized_charge_is_other_whatever_the_classifier_said():
    assert status(run("software_subscription", kind="Lodging", itemized=False))["DOC-03"] == "not_applicable"


def test_doc03_covers_every_type_in_the_table():  # hand-copied from the DOC-03 table
    assert {k: sorted(v) for k, v in COVERS.items()} == {
        "Meals - Individual": ["alcohol", "food_beverage"], "Meals - Team": ["alcohol", "food_beverage"],
        "Client Entertainment": ["alcohol", "food_beverage"], "Client Gifts": ["gift", "gift_card", "jewelry"],
        "Lodging": ["ground_transport", "laundry_service", "lodging"],
        "Travel - Other": ["clothing", "ground_transport", "health_otc", "laundry_service", "personal_care"],
        "Office Supplies": ["computer_accessory", "office_supplies"],
        "Computer Equipment": ["computer_accessory", "personal_electronics", "software_subscription"],
        "Software": ["software_subscription"]}


def test_doc03_unknown_category_is_an_error():
    with pytest.raises(ValueError):
        run("food_beverge")


def test_unknown_expense_type_costs_doc03_alone():  # "Airfare" is not in the DOC-03 table
    checks = run("airfare", "service_fee", kind="Airfare", total=100.0, itemized=False, currency="EUR", rate=None)
    assert status(checks) == {"DOC-01": "fired", "DOC-02": "not_fired", "DOC-03": "not_applicable", "DOC-04": "fired"}
    checks = run("airfare", kind="Airfare", total=100.0, currency="EUR", rate=None)  # itemized: DOC-03 cannot decide
    assert [(c.rule_id, c.status, c.kind) for c in checks] == [
        ("DOC-01", "not_fired", "exception"), ("DOC-02", "not_fired", "exception"),
        ("ERR-DOC-03", "fired", "signal"), ("DOC-04", "fired", "exception")]
    assert "'Airfare'" in checks[2].detail and verdict(checks) == "flag"


def test_rcp023_declared_airfare_still_flags_doc01():
    r = {**RECEIPTS["RCP-023"], "submitted_expense_type": "Airfare"}
    checks = documentation_checks(r, {"RCP-023-L1": "other"})
    assert fired(checks) == {"DOC-01": ("medium", ())} and status(checks)["DOC-03"] == "not_applicable"


def test_missing_category_fails_closed():
    r, _ = receipt("food_beverage")
    with pytest.raises(KeyError):
        documentation_checks(r, {})


# --- DOC-04: foreign currency needs currency and rate -------------------------------------------

def test_doc04_foreign_receipt_without_rate_fires_medium():
    checks = run("food_beverage", currency="EUR", rate=None, usd=54.0)
    assert fired(checks) == {"DOC-04": ("medium", ())}


@pytest.mark.parametrize("currency", [None, "", " "])
def test_doc04_missing_currency_fires(currency):
    assert "DOC-04" in fired(run("food_beverage", currency=currency))


@pytest.mark.parametrize("currency", ["USD", "usd", " USD"])
def test_doc04_does_not_apply_to_usd(currency):
    assert status(run("food_beverage", currency=currency, rate=None))["DOC-04"] == "not_applicable"


def test_doc04_foreign_receipt_with_rate_passes():
    assert status(run("food_beverage", currency="JPY", rate=0.0067))["DOC-04"] == "not_fired"


@pytest.mark.parametrize("rate", [0, -1.08, "1.08", True, float("nan")])
def test_doc04_bad_rate_is_an_error(rate):
    with pytest.raises(ValueError):
        run("food_beverage", currency="EUR", rate=rate)


def test_money_keeps_decimal_precision():
    assert "DOC-01" not in fired(run("other", total=Decimal("75.00"), itemized=False))


# --- Real receipts, with categories written by hand (the answer key is not read) -----------------

F, A, S = "food_beverage", "alcohol", "service_fee"
CATS = {  # one category per line, in line order
    "RCP-001": [F, F, F, S], "RCP-002": [F, A, S], "RCP-003": ["computer_accessory", "office_supplies", "office_supplies"],
    "RCP-004": [F, F, F, F], "RCP-005": ["lodging", "lodging", "ground_transport"], "RCP-006": ["computer_accessory"],
    "RCP-007": [F, F, S], "RCP-008": [F, F, F], "RCP-009": ["laundry_service"], "RCP-010": [F, A, S],
    "RCP-011": [A, F], "RCP-012": ["personal_electronics"], "RCP-013": ["gift_card", "gift"],
    "RCP-014": ["household_goods", "household_goods", "household_goods", A], "RCP-015": [F, A, S],
    "RCP-016": [F, A, S], "RCP-017": ["personal_care", S], "RCP-018": ["jewelry"],
    "RCP-019": ["personal_electronics", "personal_electronics"], "RCP-020": [F, F, F, S], "RCP-021": [F, F, F, S],
    "RCP-022": [F, "gift"], "RCP-023": ["other"], "RCP-024": ["tobacco", F, F], "RCP-025": [F, A, F],
    "RCP-026": ["computer_accessory", "computer_accessory"], "RCP-027": ["clothing", "clothing"],
    "RCP-028": ["health_otc", "health_otc"], "RCP-029": [F, F, S], "RCP-030": [F, F, S],
    "RCP-031": ["laundry_service"], "RCP-032": ["software_subscription"],
}
EXPECTED = {  # from the DOC rules; every other receipt fires none
    "RCP-012": {"DOC-03": ("medium", ())}, "RCP-014": {"DOC-03": ("medium", ())},
    "RCP-017": {"DOC-03": ("medium", ())}, "RCP-023": {"DOC-01": ("medium", ())},
}


def real_cats(r):
    return {li["line_id"]: c for li, c in zip(r["line_items"], CATS[r["receipt_id"]], strict=True)}


@pytest.mark.parametrize("r", load_receipts(), ids=lambda r: r["receipt_id"])
def test_real_receipts(r):
    assert fired(documentation_checks(r, real_cats(r))) == EXPECTED.get(r["receipt_id"], {})


def test_real_non_itemized_receipt_is_other_even_if_called_food():  # RCP-023
    r = RECEIPTS["RCP-023"]
    checks = documentation_checks(r, {"RCP-023-L1": F})
    assert status(checks)["DOC-03"] == "not_applicable" and fired(checks) == {"DOC-01": ("medium", ())}


def test_taxonomy_is_the_classifiers_category_table():
    from validator.classifier import _ROWS
    from validator.rules.documentation import TAXONOMY
    assert TAXONOMY == {c for c, _, _ in _ROWS}
