"""Multi-model comparison of the line classifier on the 32 receipts of data_split/receipts_input.jsonl.

For each OpenRouter model id: classifier (provider openrouter) + engine, with its OWN cache (.cache/compare/<slug>)
and OWN output (output/compare/<slug>/). Then the existing evaluation code scores each run against the answer key
(read for that step only) and writes output/compare/summary.json and SUMMARY.md. output/EVAL.md is never touched.

    python scripts/compare_models.py [--models M ...] [--budget USD per model] [--cap USD total] [--dry-run]

A model that rejects temperature or structured outputs does not crash the run: the classifier already drops
temperature when an endpoint lacks it and fails closed (recorded per model) when no endpoint has json_schema.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from unittest import mock

import httpx

from validator import classifier
from validator.classifier import classify
from validator.engine import run_engine
from validator.evaluation import evaluate
from validator.gold import load_gold
from validator.loader import load_receipts
from validator.normaliser import normalise_receipt
from validator.reporter import report
from validator.run import to_markdown

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data_split" / "receipts_input.jsonl"
CACHE = ROOT / ".cache" / "compare"
OUT = ROOT / "output" / "compare"
PRICES = {  # USD per MTok (in, out)
    "anthropic/claude-haiku-5.5": (0.10, 0.50),
    "openai/gpt-6-luna": (0.10, 0.50),
    "deepseek/deepseek-v4.1-flash": (0.04, 0.50),
    "qwen/qwen3.8-omni-flash": (0.15, 0.47),
    "mistralai/mistral-large-4-0": (0.70, 2.10),
    "anthropic/claude-sonnet-5.5": (2.00, 10.00),
}
TOKENS = (97_000, 6_500)  # in / out per 32-receipt run
CAVEATS = [
    "Single run per model (temperature 0 where accepted, otherwise the provider default): no variance estimate.",
    "Only 28 scored receipts (9 pass, 16 flag, 3 review); one receipt is 3.6 points of disposition accuracy.",
    "The engine was written with these answers in view, so differences between models isolate the classifier, "
    "but absolute numbers are optimistic and not a held-out estimate.",
    "A model that fails closed on a receipt is scored on its fail-closed fallback (all lines other, review).",
    "Spend is the usage.cost OpenRouter reports; latency is wall time of the whole classify call, cache misses only.",
]


def slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", model).strip("-")


def estimate(model: str) -> float:
    pin, pout = PRICES.get(model, (4.0, 20.0))
    return (TOKENS[0] * pin + TOKENS[1] * pout) / 1e6


def fake_client() -> httpx.Client:
    """Offline OpenRouter stand-in: every line food_beverage/high, cost 0."""
    def handle(req: httpx.Request) -> httpx.Response:
        if req.method == "GET":
            return httpx.Response(200, json={"data": {"endpoints": [{"supported_parameters": ["structured_outputs", "temperature"],
                                                                      "pricing": {"prompt": "0", "completion": "0"}}]}})
        user = json.loads(json.loads(req.content)["messages"][1]["content"])
        lines = [{"line_id": li["line_id"], "description_en": li["description"], "category": "food_beverage", "other_kind": "none",
                  "note": None, "confidence": "high", "recipient_kind": None, "recipient_name": None} for li in user["line_items"]]
        return httpx.Response(200, json={"id": "fake", "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0},
                                         "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"lines": lines})}}]})
    return httpx.Client(base_url=classifier.OPENROUTER_URL, transport=httpx.MockTransport(handle))


def score(results: dict, cats: dict, gold: dict) -> dict:
    with mock.patch.object(evaluate, "bootstrap", lambda *a, **k: (0.0, 0.0)):  # intervals are not reported here
        m = evaluate.measures(results, cats, gold)
    k = lambda key: (m[key]["k"], m[key]["n"])  # noqa: E731
    return {"disposition_acc": k("disposition"), "false_positives_of_pass": k("fp_of_pass"),
            "missed_of_flag": k("missed_of_flag"), "category_acc": k("cat_acc"),
            "macro_f1": m["macro_f1"], "restricted_f1": m["restricted_f1"]}


def run_model(model, receipts, gold, client, out_root, cache_root, budget) -> dict:
    out, row = out_root / slug(model), {"model": model, "slug": slug(model)}
    t0 = time.monotonic()
    try:
        c = classify(receipts, model=model, provider="openrouter", client=client, cache_dir=cache_root / slug(model),
                     budget_usd=budget)
        row["latency_s"] = round(time.monotonic() - t0, 2)
        m = c.meta
        row.update(calls=m["calls"], cache_hits=m["cache_hits"], spend_usd=round(m["cost_usd"], 6),
                   failures=len(m["failures"]), failure_reasons=dict(sorted(m["failures"].items())),
                   request_extras=m.get("request_extras"))
        results = run_engine(receipts, c.categories, gift_for=c.gift_for, uncertain=c.uncertain)
        reports = [{**report(r, results[r["receipt_id"]], c), "provider": "openrouter"} for r in receipts]
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in reports), encoding="utf-8")
        (out / "report.md").write_text(to_markdown(reports, {r["receipt_id"]: r for r in receipts}), encoding="utf-8")
        row.update(score(results, c.categories, gold))
    except Exception as exc:  # one model's failure never stops the others
        row.update(error=f"{type(exc).__name__}: {exc}", latency_s=round(time.monotonic() - t0, 2))
    return row


def pc(t) -> str:
    return f"{t[0]}/{t[1]} ({t[0] / t[1]:.0%})" if t and t[1] else "n/a"


def summary_md(rows: list[dict], cap: float, spent: float) -> str:
    out = ["# Model comparison (classifier only, same engine)", "",
           f"Receipts: {INPUT.name} (32; 28 scored). Total spend ${spent:.4f} of ${cap} cap.", "",
           "| model | disposition acc | FP of 9 pass | missed of 16 flag | line category acc | macro F1 | restricted F1 | spend USD | latency s | calls | failures |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "disposition_acc" not in r:
            out.append(f"| {r['model']} | {r.get('error') or r.get('skipped', 'not run')} |" + " |" * 9)
            continue
        out.append(f"| {r['model']} | {pc(r['disposition_acc'])} | {r['false_positives_of_pass'][0]}/{r['false_positives_of_pass'][1]} | "
                   f"{r['missed_of_flag'][0]}/{r['missed_of_flag'][1]} | {pc(r['category_acc'])} | {r['macro_f1']:.3f} | "
                   f"{r['restricted_f1']:.3f} | {r['spend_usd']:.4f} | {r['latency_s']} | {r['calls']} | {r['failures']} |")
    return "\n".join([*out, "", "## Caveats", "", *(f"- {c}" for c in CAVEATS), ""])


def main(argv=None, client=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts/compare_models.py")
    ap.add_argument("--models", nargs="+", default=list(PRICES))
    ap.add_argument("--receipts", type=Path, default=INPUT)
    ap.add_argument("--budget", type=float, default=0.30, help="max USD per model")
    ap.add_argument("--cap", type=float, default=1.50, help="max USD in total; the run stops once it is reached")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--cache", type=Path, default=CACHE)
    ap.add_argument("--dry-run", action="store_true", help="plan, estimate, and run the pipeline on a fake client (offline)")
    a = ap.parse_args(argv)

    est = {m: estimate(m) for m in a.models}
    print(f"{'model':40} est. USD / 32 receipts")
    for m in a.models:
        print(f"{m:40} {est[m]:.4f}")
    print(f"{'total':40} {sum(est.values()):.4f}  (cap {a.cap}, per-model budget {a.budget})")
    receipts = [normalise_receipt(r) for r in load_receipts(a.receipts)]
    gold = load_gold()
    if a.dry_run:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for m in a.models:
                r = run_model(m, receipts, gold, fake_client(), Path(tmp) / "out", Path(tmp) / "cache", a.budget)
                print(f"dry run {m}: {r.get('error') or 'pipeline ok'}, calls {r.get('calls')}, failures {r.get('failures')}")
        return 0
    if client is None:
        import os
        if not os.environ.get("OPENROUTER_API_KEY"):
            sys.exit("OPENROUTER_API_KEY is not set (put it in .env and export it); use --dry-run to test offline")
    rows, spent = [], 0.0
    for m in a.models:
        if spent >= a.cap:
            rows.append({"model": m, "skipped": f"global cap ${a.cap} reached"})
            continue
        r = run_model(m, receipts, gold, client or classifier._client("openrouter"), a.out, a.cache, min(a.budget, a.cap - spent))
        spent += r.get("spend_usd", 0.0)
        rows.append(r)
        print(f"{m}: spend ${r.get('spend_usd', 0):.4f}, failures {r.get('failures')}, {r.get('error', '')}")
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "summary.json").write_text(json.dumps({"total_spend_usd": round(spent, 6), "cap_usd": a.cap, "models": rows,
                                                    "caveats": CAVEATS}, indent=2), encoding="utf-8")
    (a.out / "SUMMARY.md").write_text(summary_md(rows, a.cap, spent), encoding="utf-8")
    print(f"-> {a.out}")
    return 1 if spent > a.cap else 0


if __name__ == "__main__":
    sys.exit(main())
