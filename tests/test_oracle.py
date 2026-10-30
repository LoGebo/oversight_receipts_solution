from validator.check import Check
from validator.engine import Result
from validator.evaluation.oracle import compare, run

from conftest import synthetic


def test_oracle_only_misses_the_gift_hook_limit():
    # Perfect categories, no gift_for hook: the one known miss is GIFT-04 on RCP-022 (who it is for
    # lives only in the line text). Any other row is an engine regression.
    results, gold = run()
    assert compare(results, gold) == [
        ("RCP-022", "disposition", "flag", "pass"),
        ("RCP-022", "missed exception", "GIFT-04", "-"),
    ]


def test_compare_every_branch_and_skips_out_of_scope():
    results, gold, _ = synthetic()
    assert compare(results, gold) == [
        ("T-1", "disposition", "pass", "review"),
        ("T-1", "extra signal", "-", "EXC-03"),
        ("T-2", "extra exception", "-", "TECH-01"),
        ("T-2", "lines ALC-01", "T-2-L1", "T-2-L1,T-2-L2"),
        ("T-2", "extra signal", "-", "REG-05"),
        ("T-3", "error", "-", "gifts: boom"),
        ("T-3", "disposition", "flag", "review"),
        ("T-3", "missed exception", "GIFT-04", "-"),
    ]


def test_compare_line_mismatches_and_a_missed_signal():
    gold = {"T": {"labels": {"disposition": "flag", "expected_exceptions": [{"rule_id": "DOC-01", "line_ids": []}],
                             "review_signals": [{"rule_id": "MCC-02"}]}},
            "U": {"labels": {"disposition": "flag", "expected_exceptions": [{"rule_id": "TECH-01", "line_ids": ["U-L1"]}],
                             "review_signals": []}}}
    res = {"T": Result("T", "flag", (Check("DOC-01", "fired", severity="medium", line_ids=("T-L2", "T-L1")),)),
           "U": Result("U", "flag", (Check("TECH-01", "fired", severity="high", line_ids=("U-L2",)),))}
    assert compare(res, gold) == [("T", "lines DOC-01", "()", "T-L1,T-L2"), ("T", "missed signal", "MCC-02", "-"),
                                  ("U", "lines TECH-01", "U-L1", "U-L2")]
