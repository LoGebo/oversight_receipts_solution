"""What every rule returns, and how a list of results becomes a verdict."""
from dataclasses import dataclass
from typing import Literal, get_args

from validator.disposition import SEVERITIES, Disposition, Severity, disposition

Status = Literal["fired", "not_fired", "not_applicable", "superseded"]
Kind = Literal["exception", "signal"]


@dataclass(frozen=True)
class Check:
    rule_id: str
    status: Status
    kind: Kind = "exception"
    severity: Severity | None = None  # set if and only if a fired exception
    line_ids: tuple[str, ...] = ()    # lines cited as evidence; () for whole-receipt rules
    detail: str = ""                  # the numbers behind the decision, e.g. "68/4 = $17.00 <= $30"

    def __post_init__(self) -> None:
        # Literal is not enforced at runtime: a typo like kind="Exception" would otherwise count as nothing and yield "pass".
        if self.status not in get_args(Status) or self.kind not in get_args(Kind):
            raise ValueError(f"{self.rule_id}: bad status/kind {self.status!r}/{self.kind!r}")
        if self.status == "fired" and self.kind == "exception":
            if self.severity not in SEVERITIES:
                raise ValueError(f"{self.rule_id}: a fired exception needs a severity, got {self.severity!r}")
        elif self.severity is not None:
            raise ValueError(f"{self.rule_id}: only a fired exception carries a severity")
        object.__setattr__(self, "line_ids", tuple(self.line_ids))


def verdict(checks: list[Check]) -> Disposition:
    """EXC-01 over the checks that fired. Anything that did not fire (including superseded) never counts.

    All checks must belong to ONE receipt. An empty list is "pass": the caller must make sure every
    expected rule actually ran, otherwise a bug that skips the rules would pass every receipt.
    """
    ids = [c.rule_id for c in checks]
    if len(ids) != len(set(ids)):  # EXC-04: each rule appears at most once per receipt
        raise ValueError(f"duplicate rule ids: {sorted(i for i in set(ids) if ids.count(i) > 1)}")
    fired = [c for c in checks if c.status == "fired"]
    return disposition(
        [c.severity for c in fired if c.kind == "exception"],
        sum(c.kind == "signal" for c in fired),
    )
