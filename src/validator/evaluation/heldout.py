"""Held-out stress test of the LLM classifier on hand-made receipts (data_heldout/), eval-only.

The fixture's items, merchants and phrasing appear neither in the dataset nor in the taxonomy's examples,
so this measures generalisation that the dataset run (whose taxonomy examples sit in the prompt) cannot.
Run ONCE per prompt version (a blind measurement; do not tune the prompt to it):
  set -a; . ./.env; set +a; python -m validator.evaluation.heldout [--force] [--provider P] [--model M]
The record (meta and per-line predictions) goes to data_heldout/run_record.json, committed; an existing
record is never overwritten without --force. The classifier cache goes to .cache/heldout/.
Any classifier failure exits non-zero and writes no record.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from validator.classifier import BUDGET_USD, classify, default_provider
from validator.loader import load_receipts

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "data_heldout"
OUT = DIR / "run_record.json"
CACHE = ROOT / ".cache" / "heldout"


def load() -> tuple[list[dict], dict[str, dict]]:
    receipts = load_receipts(DIR / "receipts_input.jsonl")
    expected = [json.loads(x) for x in (DIR / "expected.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return receipts, {e["line_id"]: e for e in expected}


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "0/0"


def main(argv: list[str] | None = None, client=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m validator.evaluation.heldout")
    ap.add_argument("--force", action="store_true", help="overwrite an existing record")
    ap.add_argument("--provider", choices=("anthropic", "openrouter"), default=default_provider())
    ap.add_argument("--model")
    a = ap.parse_args(argv)
    if OUT.exists() and not a.force:
        sys.exit(f"{OUT} exists: it is the record of a run; pass --force to overwrite it")
    receipts, exp = load()
    c = classify(receipts, client=client, provider=a.provider, model=a.model, cache_dir=CACHE, budget_usd=BUDGET_USD)
    m = c.meta
    print(f"provider {m['provider']} model {m['model']} | calls {m['calls']} | cache hits {m['cache_hits']} | tokens in {m['input_tokens']}"
          f" out {m['output_tokens']} | spend ${m['cost_usd']:.5f} | failures {m['failures'] or 'none'}")
    if m["failures"]:
        sys.exit(f"classifier failed for {sorted(m['failures'])}: no record written")

    rows = []
    for r in receipts:
        for li in r["line_items"]:
            e, lid = exp[li["line_id"]], li["line_id"]
            got = c.categories[lid]
            rows.append({"receipt": r["receipt_id"], "line_id": lid, "language": li["language"],
                         "description_raw": li["description_raw"], "itemized": r["itemized"],
                         "expected": e["category"], "alternatives": e["acceptable_alternatives"],
                         "ambiguous": e["genuinely_ambiguous"], "predicted": got,
                         "confidence": m["confidence"].get(lid, "failed"),
                         "exact": got == e["category"], "acceptable": got in [e["category"], *e["acceptable_alternatives"]],
                         "gift_expected": e["gift_recipient"], "gift_got": c.gift_for.get(lid)})

    n = len(rows)
    clear = [x for x in rows if not x["ambiguous"]]
    amb = [x for x in rows if x["ambiguous"]]
    print(f"\nlines {n} | exact {pct(sum(x['exact'] for x in rows), n)}"
          f" | exact-or-alternative {pct(sum(x['acceptable'] for x in rows), n)}")
    print(f"non-ambiguous {len(clear)}: exact {pct(sum(x['exact'] for x in clear), len(clear))}"
          f" | exact-or-alternative {pct(sum(x['acceptable'] for x in clear), len(clear))}")
    print(f"ambiguous {len(amb)}: acceptable answer OR low {pct(sum(x['acceptable'] or x['confidence'] == 'low' for x in amb), len(amb))}"
          f" | acceptable {sum(x['acceptable'] for x in amb)} | low {sum(x['confidence'] == 'low' for x in amb)}")
    for x in amb:
        print(f"  amb {x['line_id']:<10} {x['description_raw'][:40]:<40} exp {x['expected']:<20} got {x['predicted']:<20} {x['confidence']}")

    wrong = [x for x in rows if not x["exact"]]
    print(f"\nWRONG lines (not exact) {len(wrong)}  [alt = predicted is a listed acceptable alternative]")
    for x in wrong:
        tag = "alt" if x["acceptable"] else "WRONG"
        print(f"  {tag:<5} {x['line_id']:<10} {x['description_raw'][:46]:<46} exp {x['expected']:<21} got {x['predicted']:<21}"
              f" {x['confidence']}{' (amb)' if x['ambiguous'] else ''}")

    bands = Counter(x["confidence"] for x in rows)
    print(f"\nconfidence bands: {dict(bands)}")
    for name, bad in (("not exact", wrong), ("not acceptable", [x for x in rows if not x["acceptable"]])):
        low = [x for x in rows if x["confidence"] == "low"]
        print(f"  {name:<15}: wrong lines rated low {pct(sum(x['confidence'] == 'low' for x in bad), len(bad))}"
              f" | low lines that were wrong {pct(sum(x in bad for x in low), len(low))}")
        for band in ("high", "medium", "low"):
            b = [x for x in rows if x["confidence"] == band]
            print(f"    {band:<6} lines {len(b):>3}  wrong {sum(x in bad for x in b):>3}")

    print("\ngift_for:")
    stated = [x for x in rows if x["gift_expected"]]
    for x in stated:
        ok = x["gift_got"] is not None and x["gift_got"][0] == x["gift_expected"]["kind"]
        print(f"  stated {x['line_id']:<10} exp {x['gift_expected']['kind']}/{x['gift_expected']['name']} got {x['gift_got']} {'OK' if ok else 'MISS'}")
    invented = [x for x in rows if not x["gift_expected"] and x["gift_got"]]
    print(f"  stated extracted with right kind {sum(x['gift_got'] is not None and x['gift_got'][0] == x['gift_expected']['kind'] for x in stated)}/{len(stated)}"
          f" | not-stated lines with a recipient {len(invented)}/{n - len(stated)}")
    stated_rcpt = {x["receipt"] for x in stated}
    for x in invented:
        where = "sibling of a stated line" if x["receipt"] in stated_rcpt else "receipt states no recipient"
        print(f"  invented {x['line_id']:<10} {x['description_raw'][:40]:<40} got {x['gift_got']} ({where})")

    print("\nper language (exact | exact-or-alternative):")
    by = defaultdict(list)
    for x in rows:
        by[x["language"]].append(x)
    for lang, xs in sorted(by.items()):
        print(f"  {lang}: {pct(sum(x['exact'] for x in xs), len(xs)):<14} | {pct(sum(x['acceptable'] for x in xs), len(xs))}")
    print(f"\nspend ${m['cost_usd']:.5f}")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"meta": m, "lines": rows}, ensure_ascii=False, indent=1, default=list), encoding="utf-8")


if __name__ == "__main__":
    main()
