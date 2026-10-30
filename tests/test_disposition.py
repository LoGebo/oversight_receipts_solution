import pytest

from validator.disposition import SEVERITIES, disposition

# Copied from the wording of EXC-01, not recomputed from the implementation.
CASES = [
    ([], 0, "pass"),
    ([], 1, "review"),                       # RCP-028: a signal alone
    ([], 3, "review"),
    (["low"], 0, "review"),                  # RCP-031, RCP-032: a single low exception
    (["low", "low"], 0, "review"),
    (["low"], 2, "review"),
    (["medium"], 0, "flag"),
    (["high"], 0, "flag"),
    (["critical"], 0, "flag"),               # RCP-022
    (["low", "medium"], 0, "flag"),
    (["low", "high"], 1, "flag"),            # RCP-012: exception plus MCC-02 signal
    (["high", "low"], 0, "flag"),            # order does not matter
]


@pytest.mark.parametrize("severities, signals, expected", CASES)
def test_exc01(severities, signals, expected):
    assert disposition(severities, signals) == expected


def test_accepts_any_iterable():
    assert disposition((s for s in ["high"]), 0) == "flag"


@pytest.mark.parametrize("bad", [["urgent"], ["x", None], ["High"]])
def test_unknown_severity_is_a_value_error(bad):
    with pytest.raises(ValueError):
        disposition(bad, 0)


@pytest.mark.parametrize("bad", [-1, 1.5, None, True, "2"])
def test_signal_count_must_be_a_non_negative_int(bad):
    with pytest.raises(ValueError):
        disposition([], bad)


def test_severity_order_is_the_contract():
    assert SEVERITIES == ("low", "medium", "high", "critical")
