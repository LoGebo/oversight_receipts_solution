"""CLI: load -> normalise -> classify (cached; translates too) -> retrieve + engine -> report.
Writes <out>/report.jsonl and <out>/report.md.

    python -m validator.run [--receipts PATH] [--out DIR] [--provider anthropic|openrouter] [--model M] [--budget USD]

--provider defaults to openrouter when only OPENROUTER_API_KEY is set and --out is given, else anthropic.
SAFETY: without an explicit --out the run writes the committed output/ and is cache-only (never calls a model); a
provider/model other than the committed cache's is refused. Pass --out DIR for anything else. A warm cache needs no API key and costs nothing. Any classifier failure (no key for a cache miss, API error, spend guard) stops the run with a non-zero exit and writes no report, instead
of one where every failed receipt is "review".
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from validator.classifier import BUDGET_USD, DEFAULT_MODEL, classify, default_provider
from validator.engine import run_engine
from validator.loader import INPUT, load_receipts
from validator.normaliser import normalise_receipt
from validator.reporter import report

ROOT = Path(__file__).resolve().parents[2]


class _NoKey:
    """Client stand-in when no key is set: a cache miss fails at once, without touching the network."""

    def __init__(self, env: str):
        self.env = env

    def __getattr__(self, name):
        raise RuntimeError(f"{self.env} is not set")


def _cell(text) -> str:
    """Free text in a table cell: a newline or `|` would end the row or the cell."""
    return " ".join(str(text).splitlines()).replace("|", "\\|")


def to_markdown(reports: list[dict], receipts: dict[str, dict]) -> str:
    out = ["# Expense validation report", ""]
    for rep in reports:
        r = receipts[rep["receipt_id"]]
        out += [f"## {rep['receipt_id']} — {rep['disposition'].upper()}", "",
                f"{r['merchant_name']} (MCC {r['mcc']}) · {r['submitted_expense_type']} · {r['entity']} · "
                f"{r['total_amount']} {r['currency']} = ${r['total_amount_usd']} · attendees {r['attendee_count']}", "",
                "| line | description | USD | category | restricted | confidence |", "|---|---|---|---|---|---|"]
        lang = {li["line_id"]: li["language"] for li in r["line_items"]}
        for li in rep["line_items"]:
            desc = li["description_raw"]
            if lang[li["line_id"]] != "en" and "description_en" in li:
                desc += f" (en: {li['description_en']})"
            cat = li.get("category", "?") + (f" ({li['category_detail']})" if "category_detail" in li else "")
            cat += f": {li['category_note']}" if "category_note" in li else ""
            out.append(f"| {li['line_id']} | {_cell(desc)} | {li['amount_usd']} | {_cell(cat)} | "
                       f"{li.get('restricted', '?')} | {li.get('confidence', '?')} |")
        out += ["", f"Rules considered: {', '.join(x['rule_id'] for x in rep['rules_considered'])}", ""]
        if rep.get("error"):
            out += [f"**Error (fail closed to review):** {rep['error']}", ""]
        for e in rep["exceptions"]:
            cited = "; ".join(f"{x['line_id']} \"{x['description_raw']}\" ${x['amount_usd']}" for x in e["lines"]) or "whole receipt"
            out += [f"- **{e['rule_id']}** ({e['severity']}, `{e['policy_doc']}`) — {e['explanation']}",
                    f"  - lines: {cited}", f"  - policy: > {' '.join(e['evidence'].split())}"]
        for s in rep["review_signals"]:
            out.append(f"- review signal **{s['rule_id']}** (`{s['policy_doc']}`) — {s['reason']}")
        for s in rep["superseded"]:
            out.append(f"- superseded {s['rule_id']}: {s['reason']}")
        if not (rep["exceptions"] or rep["review_signals"] or rep.get("error")):
            out.append("- no exceptions, no review signals")
        out.append("")
    return "\n".join(out)


def main(argv=None, client=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m validator.run")
    ap.add_argument("--receipts", type=Path, default=INPUT)
    ap.add_argument("--out", type=Path, default=None, help="default: output/ (committed results; cache-only runs)")
    ap.add_argument("--provider", choices=("anthropic", "openrouter"), default=None)
    ap.add_argument("--model", help="default: claude-haiku-5-5 (anthropic) or anthropic/claude-haiku-5.5 (openrouter)")
    ap.add_argument("--budget", type=float, default=BUDGET_USD, help="max USD of model calls this run")
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache" / "classifier")
    a = ap.parse_args(argv)
    default_out = a.out is None
    a.out = ROOT / "output" if default_out else a.out
    if a.provider is None:
        a.provider = "anthropic" if default_out else default_provider()
    if default_out and (a.provider != "anthropic" or a.model not in (None, DEFAULT_MODEL)):
        sys.exit(f"refusing to write the committed output/ for provider {a.provider} model {a.model or 'default'}: "
                 f"its cache differs from the committed one. Pass --out DIR to keep the results elsewhere.")
    if default_out:
        client = None  # cache-only: a miss must never become a live call that rewrites output/

    receipts = load_receipts(a.receipts)
    clean = [normalise_receipt(r) for r in receipts]                                     # 1 normaliser
    env = "OPENROUTER_API_KEY" if a.provider == "openrouter" else "ANTHROPIC_API_KEY"
    no_key = client is None and (default_out or not os.environ.get(env))
    c = classify(clean, model=a.model, provider=a.provider, client=_NoKey(env) if no_key else client,  # 2 classifier
                 cache_dir=a.cache, budget_usd=a.budget)
    m = c.meta
    if m["failures"] and no_key:
        if default_out:
            sys.exit(f"{len(m['failures'])} receipt(s) are not in the cache ({a.cache}) for {m['provider']} model {m['model']}: "
                     f"the default output/ is cache-only, pass --out DIR to make live calls.")
        sys.exit(f"{env} is not set and {len(m['failures'])} receipt(s) are not in the cache "
                 f"({a.cache}) for {m['provider']} model {m['model']}: set the key or warm the cache.")
    if m["failures"]:
        sys.exit(f"classifier failed for {len(m['failures'])} of {len(receipts)} receipt(s), no report written "
                 f"(spend ${m['cost_usd']:.4f}): " + "; ".join(f"{k}: {v}" for k, v in sorted(m["failures"].items())))
    results = run_engine(receipts, c.categories, gift_for=c.gift_for, uncertain=c.uncertain)  # 3 retriever + 4 engine
    reports = [{**report(r, results[r["receipt_id"]], c), "provider": m["provider"]} for r in receipts]  # 5 reporter

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in reports), encoding="utf-8")
    (a.out / "report.md").write_text(to_markdown(reports, {r["receipt_id"]: r for r in receipts}), encoding="utf-8")
    n = Counter(x["disposition"] for x in reports)
    print(f"{len(reports)} receipts: pass {n['pass']}, review {n['review']}, flag {n['flag']} | provider {m['provider']} model {m['model']} | "
          f"calls {m['calls']}, cache hits {m['cache_hits']} | spend ${m['cost_usd']:.4f} | "
          f"classifier failures {len(m['failures'])} | -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
