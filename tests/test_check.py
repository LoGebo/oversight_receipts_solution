from dataclasses import FrozenInstanceError

import pytest

from validator.check import Check, verdict


def test_fired_high_exception_flags():  # RCP-010
    assert verdict([Check("ALC-01", "fired", severity="high", line_ids=("RCP-010-L2",))]) == "flag"


def test_only_fired_checks_count():
    checks = [Check("ALC-01", "not_fired"), Check("ALC-03", "not_applicable"), Check("ALC-02", "superseded")]
    assert verdict(checks) == "pass"


def test_an_unfired_signal_never_counts():
    assert verdict([Check("MCC-02", "not_fired", kind="signal")]) == "pass"


def test_signal_alone_is_review():  # RCP-028
    assert verdict([Check("MCC-02", "fired", kind="signal")]) == "review"


def test_low_exception_alone_is_review():  # RCP-031
    assert verdict([Check("LAUNDRY-01", "fired", severity="low", line_ids=("RCP-031-L1",))]) == "review"


def test_signal_does_not_downgrade_an_exception():  # RCP-012
    checks = [Check("TECH-01", "fired", severity="high"), Check("MCC-02", "fired", kind="signal")]
    assert verdict(checks) == "flag"


@pytest.mark.parametrize("kwargs", [
    dict(status="fired"),                                        # exception without severity
    dict(status="fired", severity="urgent"),                     # unknown severity
    dict(status="Fired", severity="high"),                       # typo in status
    dict(status="fired", kind="Exception", severity="high"),     # typo in kind
    dict(status="fired", kind="Exception"),                      # typo in kind, nothing else wrong
    dict(status="not_fired", kind="signall"),                    # typo in kind on a check that did not fire
    dict(status="fired", kind="signal", severity="critical"),    # a signal has no severity
    dict(status="not_fired", severity="high"),                   # severity only when fired
])
def test_malformed_checks_are_rejected(kwargs):
    with pytest.raises(ValueError):
        Check("X", **kwargs)


def test_a_rule_appears_at_most_once_per_receipt():  # EXC-04
    twice = [Check("HOUSE-01", "fired", severity="medium")] * 2
    with pytest.raises(ValueError):
        verdict(twice)


def test_a_check_cannot_be_changed_after_creation():
    c = Check("HOUSE-01", "fired", severity="medium")
    with pytest.raises(FrozenInstanceError):
        c.severity = "low"


def test_line_ids_are_stored_as_a_tuple():
    c = Check("HOUSE-01", "fired", severity="medium", line_ids=["L1", "L2"])
    assert c.line_ids == ("L1", "L2")
    hash(c)  # frozen dataclasses must be hashable
