"""Oracle experiment: the engine fed the PERFECT category of every line (gold `line_labels`).

Measures the rule engine alone, with the classifier taken out. Every receipt is run (group rules
need their context); those not in gold.OUT_OF_SCOPE are scored. gift_for is None: gold line labels hold only the
category, never who a gift is for, so GIFT-03/GIFT-04 cannot fire here (known limit, not tuned).
Run: python -m validator.evaluation.oracle
"""
from validator.engine import run_engine
from validator.gold import OUT_OF_SCOPE, load_gold
from validator.loader import load_receipts


def compare(results: dict, gold: dict, stretch: bool = False) -> list[tuple[str, str, str, str]]:
    """(receipt, what, expected, got) for every mismatch on the scored receipts, or with `stretch` on the
    out-of-scope timing receipts instead (never scored)."""
    rows = []
    for rid in sorted(gold):
        if (rid in OUT_OF_SCOPE) != stretch:
            continue
        lab, res = gold[rid]["labels"], results[rid]
        if res.error:
            rows.append((rid, "error", "-", res.error))
        if res.disposition != lab["disposition"]:
            rows.append((rid, "disposition", lab["disposition"], res.disposition))
        want = {e["rule_id"]: tuple(sorted(e["line_ids"])) for e in lab["expected_exceptions"]}
        got = {c.rule_id: tuple(sorted(c.line_ids)) for c in res.checks if c.status == "fired" and c.kind == "exception"}
        for r in sorted(want.keys() - got.keys()):
            rows.append((rid, "missed exception", r, "-"))
        for r in sorted(got.keys() - want.keys()):
            rows.append((rid, "extra exception", "-", r))
        for r in sorted(want.keys() & got.keys()):
            if want[r] != got[r]:
                rows.append((rid, f"lines {r}", ",".join(want[r]) or "()", ",".join(got[r]) or "()"))
        ws = {s["rule_id"] for s in lab["review_signals"]}
        gs = {c.rule_id for c in res.checks if c.status == "fired" and c.kind == "signal"}
        for r in sorted(ws - gs):
            rows.append((rid, "missed signal", r, "-"))
        for r in sorted(gs - ws):
            rows.append((rid, "extra signal", "-", r))
    return rows


def run() -> tuple[dict, dict]:
    gold = load_gold()
    categories = {lid: lab["category"] for g in gold.values() for lid, lab in g["line_labels"].items()}
    return run_engine(load_receipts(), categories), gold


def summary(results: dict, gold: dict) -> tuple[list, str]:
    """(mismatch rows, one-line summary) over the scored receipts."""
    scored = [rid for rid in gold if rid not in OUT_OF_SCOPE]
    rows = compare(results, gold)
    exc = [(rid, e) for rid in scored for e in gold[rid]["labels"]["expected_exceptions"]]
    missed = {(r[0], r[2]) for r in rows if r[1] == "missed exception"}
    bad_lines = {(r[0], r[1][6:]) for r in rows if r[1].startswith("lines ")}
    return rows, (f"disposition {sum(results[r].disposition == gold[r]['labels']['disposition'] for r in scored)}/{len(scored)}"
                  f" | exceptions matched {len(exc) - len(missed)}/{len(exc)}, extra {sum(r[1] == 'extra exception' for r in rows)}"
                  f" | evidence exact {len(exc) - len(missed) - len(bad_lines)}/{len(exc) - len(missed)}"
                  f" | signals missed {sum(r[1] == 'missed signal' for r in rows)}, extra {sum(r[1] == 'extra signal' for r in rows)}"
                  f" | errors {sum(r[1] == 'error' for r in rows)}")


def main() -> None:
    rows, line = summary(*run())
    for row in rows:
        print("{:<8} {:<18} {:<26} {}".format(*row))
    print(f"\n{line}")

if __name__ == "__main__":
    main()
