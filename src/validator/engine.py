"""Orchestrator: runs every rule family on every receipt and turns the checks into a disposition.

D-008: `verdict([])` is "pass", so this module proves every expected rule ran (COVERAGE) and raises
if not. FAIL-CLOSED, at the finest grain: each rule family runs on its own, so a family that raises
costs only its own rules. The receipts it ran for get one fired ERR-<family> review signal in its
place (so never "pass") and keep every other family's checks, so real exceptions still flag. A rule
that cannot be decided on its own (an unknown expense type, no euro rate, no home currency) reports a
fired ERR-<rule id> review signal in that rule's place, and coverage counts it as that rule.
Cross-receipt families run per group, and a bad receipt only degrades its own group: meals per
employee and calendar date (common.day_key), REG-03 over the same day, health per trip_id, timing
per day too (TIME-03 groups it by merchant name, timing.group_key). A TIME-03 split around the meal
cap replaces that cap rule (MEAL-01, REG-02 or REG-03) on the receipts it covers: superseded, not a breach.

RETRIEVER: each Result records the retriever's candidate rules (`considered`). Every rule is still
evaluated, so a fired rule outside the candidates is a retriever recall bug: that receipt alone gets a
fired ERR-retriever review signal (fail closed per receipt); the rest of the batch is unaffected.

ERR-input: one review signal per receipt whose input figures no rule can trust (_input_issues); it is
outside the rule families and the coverage proof.

EXC-03: `uncertain` (receipt_id -> line_ids whose category is not confident) adds one EXC-03 review
signal per receipt citing those lines, and those lines are left out of every other rule.
"""
import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from validator import retriever
from validator.check import Check, verdict
from validator.disposition import Disposition
from validator.rules import alcohol, documentation, gifts, health, lines, meals, merchant, personal, regional, timing
from validator.rules.common import currency, day_key, mcc_code

FAMILIES = {  # family -> the rule ids it returns for every receipt, in report order
    "alcohol": alcohol.RULE_IDS, "merchant": merchant.RULE_IDS, "lines": lines.RULE_IDS,
    "personal": personal.RULE_IDS, "documentation": documentation.RULE_IDS, "gifts": gifts.RULE_IDS,
    "regional": regional.RULE_IDS, "meals": meals.RULE_IDS, "health": health.RULE_IDS, "timing": timing.RULE_IDS,
    "exc03": ("EXC-03",),
}
EXPECTED = frozenset(i for ids in FAMILIES.values() for i in ids)


@dataclass(frozen=True)
class Result:
    receipt_id: str
    disposition: Disposition
    checks: tuple[Check, ...] = ()
    error: str | None = None
    considered: dict[str, str] = field(default_factory=dict)  # rule_id -> why the retriever named it


def _exc03(ids: set[str]) -> Check:
    if not ids:
        return Check("EXC-03", "not_fired", kind="signal", detail="every category is confident")
    return Check("EXC-03", "fired", kind="signal", line_ids=tuple(sorted(ids)), detail="category not confident: line left out of every other rule")


def _strip(r: dict, ids: set[str]) -> dict:
    on = {li["line_id"] for li in r["line_items"]}
    if ids - on:
        raise ValueError(f"uncertain lines {sorted(ids - on)} are not on {r['receipt_id']}")
    if ids and not r["itemized"]:
        raise ValueError("EXC-03: a non-itemized charge is `other` by definition, never uncertain")
    return {**r, "line_items": [li for li in r["line_items"] if li["line_id"] not in ids]}


def _eur_usd(r: dict, receipts: list[dict]) -> float | None:
    """The EUR->USD rate of the dataset's EUR receipts on r's date; None if none or they disagree."""
    day = r.get("transaction_datetime")
    if not isinstance(day, str):
        return None
    rates = {o["fx_rate_to_usd"] for o in receipts
             if isinstance(o.get("currency"), str) and o["currency"].strip() and currency(o) == "EUR"
             and o.get("fx_rate_to_usd") is not None and str(o.get("transaction_datetime"))[:10] == day[:10]}
    return rates.pop() if len(rates) == 1 else None


def _input_issues(r: dict) -> list[str]:
    """What makes the receipt's figures untrustworthy. A missing value is not one: DOC-02/DOC-04 and the
    rule families report those. Tolerances absorb rounding: $0.05 or 1% on a total, $0.02 or 1% on a line."""
    def num(v):
        return float(v) if type(v) in (int, float) and math.isfinite(v) else None

    lines, issues = r.get("line_items") or [], []
    if r.get("itemized") is True and not lines:
        issues.append("itemized receipt with no line items")
    if mcc_code(r) is None:
        issues.append("no MCC recorded")
    fields = [(k, r.get(k)) for k in ("total_amount", "total_amount_usd")]
    fields += [(f"{li.get('line_id')} {k}", li.get(k)) for li in lines for k in ("amount", "amount_usd")]
    for label, v in fields:
        if v is not None and num(v) is None:
            issues.append(f"{label} is not a number: {v!r}")
        elif v is not None and v < 0:
            issues.append(f"{label} is negative: {v}")
    usd, total, rate = num(r.get("total_amount_usd")), num(r.get("total_amount")), num(r.get("fx_rate_to_usd"))
    line_usd = [num(li.get("amount_usd")) for li in lines]
    if lines and usd is not None and None not in line_usd and abs(sum(line_usd) - usd) > max(0.05, 0.01 * abs(usd)):
        issues.append(f"line amount_usd sum to {sum(line_usd):.2f}, total_amount_usd is {usd}")
    if rate is not None:
        for li in lines:
            a, u = num(li.get("amount")), num(li.get("amount_usd"))
            if a is not None and u is not None and abs(a * rate - u) > max(0.02, 0.01 * abs(u)):
                issues.append(f"{li.get('line_id')} amount_usd {u} != amount {a} x rate {rate}")
        if total is not None and usd is not None and abs(total * rate - usd) > max(0.05, 0.01 * abs(usd)):
            issues.append(f"total_amount_usd {usd} != total_amount {total} x rate {rate}")
    return issues


def _signal(family: str, exc: Exception) -> Check:
    return Check(f"ERR-{family}", "fired", kind="signal", detail=f"{family}: {type(exc).__name__}: {exc}")


def run_engine(receipts: list[dict], categories: dict[str, str], gift_for: dict | None = None,
               uncertain: dict[str, set[str]] | None = None) -> dict[str, Result]:
    uncertain = uncertain or {}
    rids = [r["receipt_id"] for r in receipts]
    if len(rids) != len(set(rids)) or set(uncertain) - set(rids):
        raise ValueError("duplicate receipt ids, or `uncertain` names a receipt that is not in the batch")
    all_lines = {li["line_id"] for r in receipts for li in r["line_items"]}
    if gift_for and set(gift_for) - all_lines:
        raise ValueError(f"gift_for names unknown lines {sorted(set(gift_for) - all_lines)}")

    found: dict[str, dict[str, list[Check]]] = {rid: {} for rid in rids}

    def attempt(family: str, group: list[dict], run: Callable[[], dict]) -> None:
        """`run` maps receipt_id -> its Check(s) for this family, for every receipt in `group`."""
        try:
            out = run()
        except Exception as exc:  # fail closed: the error is recorded, the other families still count
            out = {r["receipt_id"]: [_signal(family, exc)] for r in group}
        for r in group:
            got = out.get(r["receipt_id"], [])
            found[r["receipt_id"]][family] = [got] if isinstance(got, Check) else list(got)

    considered = {r["receipt_id"]: retriever.candidate_rules(r, categories, gift_for) for r in receipts}
    original = {r["receipt_id"]: r for r in receipts}
    batch = []
    for r in receipts:
        ids = set(uncertain.get(r["receipt_id"], ()))
        try:
            batch.append(_strip(r, ids))
            found[r["receipt_id"]]["exc03"] = [_exc03(ids)]
        except Exception as exc:  # the uncertain set is unusable: rules see every line
            batch.append(r)
            found[r["receipt_id"]]["exc03"] = [_signal("exc03", exc)]

    days, trips = defaultdict(list), defaultdict(list)
    for r in batch:
        days[day_key(r)].append(r)
        trips[("trip", r["trip_id"]) if r.get("trip_id") is not None else ("receipt", r["receipt_id"])].append(r)
    for g in days.values():
        attempt("meals", g, lambda g=g: meals.meal_checks(g, categories))
    for g in trips.values():
        attempt("health", g, lambda g=g: health.health_checks(g, categories))
    split: dict[str, tuple[str, ...]] = {}  # receipt_id -> thresholds its TIME-03 split is around

    def run_timing(g: list[dict]) -> dict:
        checks, around = timing.timing_checks(g, categories, gift_for, {r["receipt_id"]: _eur_usd(r, batch) for r in g})
        split.update(around)
        return checks
    for g in days.values():
        attempt("timing", g, lambda g=g: run_timing(g))

    out = {}
    for r in batch:
        rid = r["receipt_id"]
        mine = {li["line_id"] for li in r["line_items"]}
        hook = None if gift_for is None else {k: v for k, v in gift_for.items() if k in mine}
        same_day = [o for o in days[day_key(r)] if o is not r]
        per_receipt = {
            "alcohol": lambda r=r: alcohol.alcohol_checks(r, categories),
            "merchant": lambda r=r: merchant.merchant_checks(r),
            "lines": lambda r=r: lines.line_checks(r, categories),
            "personal": lambda r=r: personal.personal_checks(r, categories),
            "documentation": lambda r=r: documentation.documentation_checks(r, categories),
            "gifts": lambda r=r, hook=hook: gifts.gift_checks(r, categories, hook),
            "regional": lambda r=r, same_day=same_day: regional.regional_checks(r, categories, same_day, _eur_usd(r, batch)),
        }
        for family, run in per_receipt.items():
            attempt(family, [r], lambda run=run, rid=rid: {rid: run()})
        if "meal cap" in split.get(rid, ()):
            for f in ("meals", "regional"):
                found[rid][f] = [Check(c.rule_id, "superseded", detail=f"replaced by TIME-03, split around the meal cap ({c.detail})")
                                 if c.rule_id in timing.MEAL_CAP_RULES and c.status == "fired" else c
                                 for c in found[rid][f]]

        checks = [c for f in FAMILIES for c in found[rid].get(f, [])]
        ids = [c.rule_id.removeprefix("ERR-") if c.rule_id.removeprefix("ERR-") in EXPECTED else c.rule_id for c in checks]
        want = [i for f, fids in FAMILIES.items()
                for i in ((f"ERR-{f}",) if any(c.rule_id == f"ERR-{f}" for c in found[rid].get(f, [])) else fids)]
        if sorted(ids) != sorted(want):  # D-008: prove every rule ran, once (a failed family or rule by its ERR signal)
            raise RuntimeError(f"{rid}: coverage broken, missing {sorted(set(want) - set(ids))}, "
                               f"unexpected {sorted(set(ids) - set(want))}, {len(ids)} checks for {len(want)} rules")
        missed = sorted({c.rule_id for c in checks if c.status == "fired" and not c.rule_id.startswith("ERR-")}
                        - considered[rid].keys())
        if missed:
            checks.append(Check("ERR-retriever", "fired", kind="signal",
                                detail=f"retriever: missed rule {', '.join(missed)} (fired, not a candidate)"))
        issues = _input_issues(original[rid])
        if issues:
            checks.append(Check("ERR-input", "fired", kind="signal", detail="input: " + "; ".join(issues)))
        errors = [c.detail for c in checks if c.rule_id.startswith("ERR-")]
        out[rid] = Result(rid, verdict(checks), tuple(checks), "; ".join(errors) or None, considered[rid])
    return out
