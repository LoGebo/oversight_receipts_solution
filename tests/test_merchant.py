import pytest

from validator.check import verdict
from validator.loader import load_receipts
from validator.rules.merchant import merchant_checks


def fired(mcc):
    return {c.rule_id: (c.kind, c.severity, c.line_ids) for c in merchant_checks({"mcc": mcc}) if c.status == "fired"}


@pytest.mark.parametrize("mcc", ["5921", "5993", "7995", "7297", "5944"])
def test_high_risk_mcc_is_a_high_exception_citing_no_lines(mcc):
    assert fired(mcc) == {"MCC-01": ("exception", "high", ())}


@pytest.mark.parametrize("mcc", ["5813", "5912", "5311", "5411", "5732"])
def test_medium_risk_mcc_is_a_signal_never_an_exception(mcc):
    assert fired(mcc) == {"MCC-02": ("signal", None, ())}
    assert verdict(merchant_checks({"mcc": mcc})) == "review"


@pytest.mark.parametrize("mcc", ["5812", "7011", "4111", "4121", "5942", "5943", "5734", "7216", "9999"])
def test_low_and_unlisted_mcc_fire_nothing(mcc):  # 9999: "any MCC not listed is low risk"
    assert fired(mcc) == {}
    assert verdict(merchant_checks({"mcc": mcc})) == "pass"


def test_high_risk_alone_flags():
    assert verdict(merchant_checks({"mcc": "7995"})) == "flag"


EXPECTED = {  # hand-written from the MCC table in merchant-category-risk.md
    "RCP-011": ["MCC-01"], "RCP-012": ["MCC-02"], "RCP-013": ["MCC-02"], "RCP-014": ["MCC-02"],
    "RCP-017": ["MCC-01"], "RCP-018": ["MCC-01"], "RCP-019": ["MCC-02"], "RCP-024": ["MCC-02"],
    "RCP-027": ["MCC-02"], "RCP-028": ["MCC-02"],
}


def test_real_receipts_hit_exactly_the_table():
    hits = {r["receipt_id"]: sorted(fired(r["mcc"])) for r in load_receipts() if fired(r["mcc"])}
    assert hits == EXPECTED


@pytest.mark.parametrize("mcc", [5921, " 5921", "5921 "])
def test_mcc_that_is_not_an_exact_string_still_matches(mcc):
    assert fired(mcc) == {"MCC-01": ("exception", "high", ())}
