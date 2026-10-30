"""EXC-01: disposition is computed from the most severe exception, never judged."""
from collections.abc import Iterable
from typing import Literal, get_args

Severity = Literal["low", "medium", "high", "critical"]
SEVERITIES = get_args(Severity)  # ordered, least to most severe: the single source of truth
Disposition = Literal["flag", "review", "pass"]
_FLAG_FROM = SEVERITIES.index("medium")  # EXC-01: medium, high and critical flag


def disposition(severities: Iterable[str], n_signals: int) -> Disposition:
    """any critical/high/medium exception -> flag; only low exceptions or only signals -> review; nothing -> pass."""
    severities = list(severities)  # a generator would be consumed by the first pass below
    unknown = sorted({repr(s) for s in severities if s not in SEVERITIES})
    if unknown:
        raise ValueError(f"unknown severity {unknown}")
    if isinstance(n_signals, bool) or not isinstance(n_signals, int) or n_signals < 0:
        raise ValueError(f"n_signals must be a non-negative int, got {n_signals!r}")
    if any(SEVERITIES.index(s) >= _FLAG_FROM for s in severities):
        return "flag"
    if severities or n_signals:
        return "review"
    return "pass"
