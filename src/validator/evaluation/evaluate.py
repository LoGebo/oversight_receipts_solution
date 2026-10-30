"""Evaluation report: the brief's Part 3 measures, with 95% intervals, for three systems -> output/EVAL.md.

  A  LLM       the real classifier (warm cache only; zero cost) feeding the engine
  B  ORACLE    gold categories feeding the engine (oracle.py): the engine alone
  C  KEYWORD   the frozen keyword baseline (baseline.py) feeding the same engine
Every receipt goes through the engine (group rules need their context); those not in gold.OUT_OF_SCOPE are scored.
Exception/signal matching reuses oracle.compare (README rules: same receipt + rule_id; evidence = exact line_ids).

Intervals: proportions get Clopper-Pearson (exact, two-sided 95%). Chosen over Wilson because with n
between 3 and 65 and many 0/n or n/n results we want guaranteed coverage, not average coverage; Wilson
is computed alongside for the headline rates. Disposition accuracy and macro F1 also get a percentile
bootstrap (10,000 resamples of RECEIPTS, fixed seed), since lines on one receipt are not independent.
Run: python -m validator.evaluation.evaluate [--allow-calls]   (without the flag a cache miss is fatal)
"""
import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path
from statistics import NormalDist

from validator.classifier import CATEGORIES, RESTRICTED, classify
from validator.engine import run_engine
from validator.evaluation import baseline, oracle
from validator.gold import OUT_OF_SCOPE, load_gold
from validator.loader import load_receipts
from validator.rules.documentation import EXTENSIONS

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "output" / "EVAL.md"
HELDOUT = {"v1": ROOT / "data_heldout" / "run_record_prompt_v1.json", "v2": ROOT / "data_heldout" / "run_record_prompt_v2.json",
           "v3": ROOT / "data_heldout" / "run_record.json"}
HELDOUT_INPUT = ROOT / "data_heldout" / "receipts_input.jsonl"
SEED, B =20261026, 10_000
DISP = ("flag", "review", "pass")
SYSTEMS = ("A LLM", "B ORACLE", "C KEYWORD")
PREVALENCES = (0.01, 0.03, 0.10)
BANDS = ("high", "medium", "low")


# ---------- statistics (stdlib only) ----------

def _cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def _bisect(f, target: float) -> float:
    """p in [0, 1] with f(p) = target, f increasing."""
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < target else (lo, mid)
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if not 0 <= k <= n or n == 0:
        raise ValueError(f"need 0 <= k <= n and n > 0, got {k}/{n}")
    lo = 0.0 if k == 0 else _bisect(lambda p: 1 - _cdf(k - 1, n, p), alpha / 2)
    hi = 1.0 if k == n else _bisect(lambda p: 1 - _cdf(k, n, p), 1 - alpha / 2)
    return lo, hi


def wilson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if not 0 <= k <= n or n == 0:
        raise ValueError(f"need 0 <= k <= n and n > 0, got {k}/{n}")
    z = NormalDist().inv_cdf(1 - alpha / 2)
    c = (k + z * z / 2) / (n + z * z)
    h = z * math.sqrt(k * (n - k) / n + z * z / 4) / (n + z * z)
    return max(0.0, c - h), min(1.0, c + h)


def bootstrap(units: list, stat, b: int = B, seed: int = SEED) -> tuple[float, float]:
    """Percentile 95% CI of stat(resample of units), resampling units with replacement."""
    rng = random.Random(seed)
    vals = sorted(stat(rng.choices(units, k=len(units))) for _ in range(b))
    return vals[round(0.025 * (b - 1))], vals[round(0.975 * (b - 1))]


def ppv(sens: float, spec: float, prev: float) -> float:
    tp, fp = sens * prev, (1 - spec) * (1 - prev)
    return tp / (tp + fp) if tp + fp else float("nan")


def mcnemar(b: int, c: int) -> float:
    n = b + c
    return min(1.0, 2 * _cdf(min(b, c), n, 0.5)) if n else 1.0


# ---------- systems ----------

class _NoNetwork:
    @property
    def messages(self):
        raise RuntimeError("cache miss: evaluate.py makes no model calls without --allow-calls")


def run_systems(allow_calls: bool = False) -> tuple[dict, dict, dict, dict, list]:
    """{system: results}, {system: line categories or None}, LLM info, gold, receipts."""
    receipts, gold = load_receipts(), load_gold()
    c = classify(receipts, client=None if allow_calls else _NoNetwork(), cache_dir=ROOT / ".cache" / "classifier")
    if c.meta["calls"] and not allow_calls:
        sys.exit(f"classifier cache misses for {sorted(c.meta['failures'])}: rerun with --allow-calls (costs money)")
    if c.meta["failures"]:
        sys.exit(f"classifier failures {c.meta['failures']}: the measurement would score fail-closed fallbacks")
    kw = baseline.classify(receipts)
    results = {
        "A LLM": run_engine(receipts, c.categories, gift_for=c.gift_for, uncertain=c.uncertain),
        "B ORACLE": oracle.run()[0],
        "C KEYWORD": run_engine(receipts, kw),
    }
    info = {k: c.meta[k] for k in ("confidence", "model", "prompt_version")}
    return results, {"A LLM": c.categories, "B ORACLE": None, "C KEYWORD": kw}, \
        {**info, "gift_for": c.gift_for}, gold, receipts


# ---------- measures ----------

def prop(k: int, n: int) -> dict:
    return {"k": k, "n": n, "p": k / n if n else None, "cp": clopper_pearson(k, n) if n else None,
            "wilson": wilson(k, n) if n else None}


def macro_f1(pairs: list[tuple[str, str]]) -> float:
    """Mean per-category F1 over the categories in the correct answers (a class never predicted scores 0)."""
    f = []
    for c in sorted({g for g, _ in pairs}):
        tp = sum(g == c and p == c for g, p in pairs)
        fp = sum(g != c and p == c for g, p in pairs)
        fn = sum(g == c and p != c for g, p in pairs)
        f.append(2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0)
    return sum(f) / len(f)


def f1_binary(pairs: list[tuple[bool, bool]]) -> float:
    tp = sum(g and p for g, p in pairs)
    d = 2 * tp + sum(p and not g for g, p in pairs) + sum(g and not p for g, p in pairs)
    return 2 * tp / d if d else 0.0


def scored_ids(gold: dict) -> list[str]:
    return sorted(r for r in gold if r not in OUT_OF_SCOPE)


def measures(results: dict, cats: dict | None, gold: dict) -> dict:
    scored = scored_ids(gold)
    want = {r: gold[r]["labels"]["disposition"] for r in scored}
    got = {r: results[r].disposition for r in scored}
    m = {"confusion": Counter((want[r], got[r]) for r in scored)}
    ok = m["ok"] = {r: want[r] == got[r] for r in scored}
    m["disposition"] = prop(sum(ok.values()), len(scored))
    m["disposition_boot"] = bootstrap(scored, lambda s: sum(ok[r] for r in s) / len(s))
    for d in DISP:
        m[f"{d}_precision"] = prop(sum(got[r] == d == want[r] for r in scored), sum(got[r] == d for r in scored))
        m[f"{d}_recall"] = prop(sum(got[r] == d == want[r] for r in scored), sum(want[r] == d for r in scored))
    m["fp_of_pass"] = prop(sum(want[r] == "pass" != got[r] for r in scored), sum(want[r] == "pass" for r in scored))
    m["missed_of_flag"] = prop(sum(want[r] == "flag" != got[r] for r in scored), sum(want[r] == "flag" for r in scored))
    # base-rate inputs: (i) alarm = flag, condition = gold flag; (ii) alarm = not pass, condition = gold not pass
    m["sens_flag"] = m["flag_recall"]
    m["spec_flag"] = prop(sum(want[r] != "flag" and got[r] != "flag" for r in scored), sum(want[r] != "flag" for r in scored))
    m["sens_any"] = prop(sum(want[r] != "pass" and got[r] != "pass" for r in scored), sum(want[r] != "pass" for r in scored))
    m["spec_any"] = prop(sum(want[r] == got[r] == "pass" for r in scored), sum(want[r] == "pass" for r in scored))

    rows = oracle.compare(results, gold)
    m["errors"] = sum(x[1] == "error" for x in rows)
    exp = [(r, e["rule_id"]) for r in scored for e in gold[r]["labels"]["expected_exceptions"]]
    missed = {(x[0], x[2]) for x in rows if x[1] == "missed exception"}
    extra = [(x[0], x[3]) for x in rows if x[1] == "extra exception"]
    bad_lines = {(x[0], x[1][6:]) for x in rows if x[1].startswith("lines ")}
    matched = len(exp) - len(missed)
    m["exc_precision"] = prop(matched, matched + len(extra))
    m["exc_recall"] = prop(matched, len(exp))
    m["evidence_exact"] = prop(matched - len(bad_lines), matched)
    sig = [(r, s["rule_id"]) for r in scored for s in gold[r]["labels"]["review_signals"]]
    s_missed = sum(x[1] == "missed signal" for x in rows)
    s_extra = [x for x in rows if x[1] == "extra signal"]
    m["sig_precision"] = prop(len(sig) - s_missed, len(sig) - s_missed + len(s_extra))
    m["sig_recall"] = prop(len(sig) - s_missed, len(sig))
    m["exc03_signals"] = sum(x[3] == "EXC-03" for x in s_extra)
    per_rule = {}
    for rule in sorted({e for _, e in exp} | {e for _, e in extra}):
        n_exp = sum(e == rule for _, e in exp)
        hit = n_exp - sum(e == rule for _, e in missed)
        per_rule[rule] = (hit, hit + sum(e == rule for _, e in extra), n_exp)
    m["per_rule"] = per_rule

    if cats is not None:
        lines = []
        for r in scored:
            for lid, gl in gold[r]["line_labels"].items():
                c = EXTENSIONS.get(cats[lid], cats[lid])
                lines.append((r, gl["category"], c, gl["restricted"], RESTRICTED[c], lid))
        by_r = {r: [x for x in lines if x[0] == r] for r in scored}
        m["lines"] = lines
        m["cat_acc"] = prop(sum(x[1] == x[2] for x in lines), len(lines))
        m["restricted_acc"] = prop(sum(x[3] == x[4] for x in lines), len(lines))
        m["macro_f1"] = macro_f1([(x[1], x[2]) for x in lines])
        m["macro_f1_boot"] = bootstrap(scored, lambda s: macro_f1([(x[1], x[2]) for r in s for x in by_r[r]]))
        m["restricted_f1"] = f1_binary([(x[3], x[4]) for x in lines])
        m["restricted_f1_boot"] = bootstrap(scored, lambda s: f1_binary([(x[3], x[4]) for r in s for x in by_r[r]]))
        m["n_classes"] = len({x[1] for x in lines})
    return m


def disposition_discordance(ms: dict) -> tuple[int, int]:
    """(receipts A right and C wrong, receipts C right and A wrong)."""
    a, c = ms["A LLM"]["ok"], ms["C KEYWORD"]["ok"]
    return sum(a[r] and not c[r] for r in a), sum(c[r] and not a[r] for r in a)


MEASURES_HIGHER = [  # (name, key, higher is better)
    ("disposition accuracy", "disposition", True), ("false positives", "fp_of_pass", False),
    ("missed violations", "missed_of_flag", False), ("exception precision", "exc_precision", True),
    ("exception recall", "exc_recall", True), ("evidence exact", "evidence_exact", True),
    ("signal precision", "sig_precision", True), ("signal recall", "sig_recall", True),
    ("category accuracy", "cat_acc", True), ("restricted accuracy", "restricted_acc", True),
    ("macro F1", "macro_f1", True), ("restricted F1", "restricted_f1", True),
]


def _val(x):
    return x["p"] if isinstance(x, dict) else x


def keyword_better(a: dict, c: dict) -> list[str]:
    """Measures where C's point estimate beats A's."""
    return [name for name, key, hi in MEASURES_HIGHER if _val(c[key]) is not None and _val(a[key]) is not None
            and _val(c[key]) != _val(a[key]) and (_val(c[key]) > _val(a[key])) == hi]


def fired_rules(result) -> list[str]:
    return sorted(c.rule_id for c in result.checks if c.status == "fired")


def heldout_measures(d: dict) -> dict:
    rows = d["lines"]
    clear = [x for x in rows if not x["ambiguous"]]
    amb = [x for x in rows if x["ambiguous"]]
    wrong = [x for x in rows if not x["exact"]]
    stated = [x for x in rows if x["gift_expected"]]
    m = {"Exact category, all lines": prop(sum(x["exact"] for x in rows), len(rows)),
         "Exact or listed alternative, all lines": prop(sum(x["acceptable"] for x in rows), len(rows)),
         "Exact, non-ambiguous lines": prop(sum(x["exact"] for x in clear), len(clear)),
         "Ambiguous lines: acceptable answer or rated low": prop(
             sum(x["acceptable"] or x["confidence"] == "low" for x in amb), len(amb)),
         "Non-exact lines rated low (would raise EXC-03)": prop(sum(x["confidence"] == "low" for x in wrong), len(wrong))}
    for band in BANDS:
        b = [x for x in rows if x["confidence"] == band]
        m[f"Exact when confidence = {band}"] = prop(sum(x["exact"] for x in b), len(b))
    m["Stated recipients extracted with the right kind"] = prop(
        sum(bool(x["gift_got"]) and x["gift_got"][0] == x["gift_expected"]["kind"] for x in stated), len(stated))
    m["Lines with no stated recipient given one anyway"] = prop(
        sum(bool(x["gift_got"]) for x in rows if not x["gift_expected"]), len(rows) - len(stated))
    return m


def _fired(result) -> dict[str, tuple]:
    return {c.rule_id: c.line_ids for c in result.checks if c.status == "fired"}


def rule_change(ref, got) -> str:
    """What changes between two engine results for one receipt, in words."""
    a, b = _fired(ref), _fired(got)
    out = [f"{ref.disposition} -> {got.disposition}"] if ref.disposition != got.disposition else []
    for rule in sorted(a.keys() | b.keys()):
        if rule not in b:
            out.append(f"{rule} no longer fires")
        elif rule not in a:
            out.append(f"{rule} fires" + (f" on {', '.join(b[rule])}" if b[rule] else ""))
        elif a[rule] != b[rule]:
            out.append(f"{rule} cites {', '.join(b[rule]) or 'no line'} instead of {', '.join(a[rule]) or 'no line'}")
    return ", ".join(out)


def heldout_failures(rec: dict, receipts: list[dict]) -> dict:
    """Engine consequences of the held-out classifier errors. Reference run: the annotator's categories and
    recipients. Each error source is swapped in alone, the other held at the annotator's value."""
    rows = rec["lines"]
    exp = {x["line_id"]: x["expected"] for x in rows}
    pred = {x["line_id"]: x["predicted"] for x in rows}
    stated = {x["line_id"]: (x["gift_expected"]["kind"], x["gift_expected"]["name"]) for x in rows if x["gift_expected"]}
    got = {x["line_id"]: tuple(x["gift_got"]) for x in rows if x["gift_got"]}
    spurious = [x for x in rows if x["gift_got"] and not x["gift_expected"]]
    ref = run_engine(receipts, exp, gift_for=stated)

    def changes(cats, gift):
        res = run_engine(receipts, cats, gift_for=gift)
        return {r: rule_change(ref[r], res[r]) for r in ref if rule_change(ref[r], res[r])}

    official = {**stated, **{x["line_id"]: ("government_official", x["gift_got"][1]) for x in spurious}}
    res = run_engine(receipts, exp, gift_for=official)
    gift04 = sorted({lid for r in res.values() for c in r.checks if c.rule_id == "GIFT-04" and c.status == "fired"
                     for lid in c.line_ids} & {x["line_id"] for x in spurious})
    wrong = [x for x in rows if not x["exact"]]
    flips = [x for x in wrong if RESTRICTED[EXTENSIONS.get(x["expected"], x["expected"])]
             != RESTRICTED[EXTENSIONS.get(x["predicted"], x["predicted"])]]
    return {"wrong": wrong, "flips": flips, "spurious": spurious, "by_category": changes(pred, stated),
            "by_recipient": changes(exp, {**stated, **got}), "gift04_if_official": gift04}


# ---------- report ----------

def pct(x: float | None) -> str:
    return "n/a" if x is None or math.isnan(x) else f"{100 * x:.1f}%"


def fmt(p: dict, wilson_too: bool = False) -> str:
    if not p["n"]:
        return "0/0 (n/a)"
    s = f"{p['k']}/{p['n']} = {pct(p['p'])} [{pct(p['cp'][0])}, {pct(p['cp'][1])}]"
    return s + (f" W[{pct(p['wilson'][0])}, {pct(p['wilson'][1])}]" if wilson_too else "")


def kf(p: dict) -> str:
    return f"{p['k']}/{p['n']}"


def heldout_section(records: dict) -> list[str]:
    if not records:
        return ["(no record in data_heldout/: held-out stress test not summarised)"]
    ms = {v: heldout_measures(d) for v, d in records.items()}
    vs = list(records)
    out = ["The held-out set is hand-made receipts whose items, merchants and phrasing appear neither in the dataset "
           "nor in the taxonomy's examples, so it measures what the dataset run cannot: generalisation of the classifier. "
           "**One annotator** wrote its expected labels, acceptable alternatives and ambiguity flags: they are one "
           "person's judgement, not an agreed answer key. Each prompt version was run once."]
    if len(vs) > 1:
        prev, ex = vs[-2], "Exact category, all lines"
        out[0] += (f" Each later run used the same lines after the earlier results had been seen, and the set was used to "
                   f"choose between prompts, so the {vs[-1]} figures are a repeated measurement of the same set, not a fresh "
                   f"blind test. {prev} -> {vs[-1]}: exact category {kf(ms[prev][ex])} -> {kf(ms[vs[-1]][ex])}, exact or "
                   f"listed alternative {kf(ms[prev]['Exact or listed alternative, all lines'])} -> "
                   f"{kf(ms[vs[-1]]['Exact or listed alternative, all lines'])}.")
    out += ["", "| Run | " + " | ".join(vs) + " |", "|---|" + "---|" * len(vs)]
    out.append("| Model, prompt | " + " | ".join(f"{records[v]['meta']['model']}, {records[v]['meta']['prompt_version']}" for v in vs) + " |")
    out.append("| Calls, spend | " + " | ".join(f"{records[v]['meta']['calls']}, ${records[v]['meta']['cost_usd']:.4f}" for v in vs) + " |")
    out += [f"| {name} | " + " | ".join(fmt(ms[v][name]) for v in vs) + " |" for name in ms[vs[-1]]]
    wrong = Counter(x["confidence"] for x in records[vs[-1]]["lines"] if not x["exact"])
    out += ["", f"Calibration ({vs[-1]}): the non-exact lines were rated " + ", ".join(f"{b} {n}" for b, n in sorted(wrong.items()))
            + f"; only `low` raises EXC-03, so {wrong['low']} of {sum(wrong.values())} would have reached a reviewer through "
            "the uncertainty route. Rating a wrong answer `medium` is the classifier error the engine cannot see."]
    if len(vs) > 1:
        old = {x["line_id"]: x for x in records[prev]["lines"]}
        changed = [(old[x["line_id"]], x) for x in records[vs[-1]]["lines"]
                   if (x["predicted"], x["confidence"]) != (old[x["line_id"]]["predicted"], old[x["line_id"]]["confidence"])
                   and not (x["exact"] and old[x["line_id"]]["exact"])]
        out += ["", f"Lines where {prev} and {vs[-1]} differ, other than confidence changes on lines both got exactly right:", "",
                f"| Line | Description | Expected | {prev} | {vs[-1]} |", "|---|---|---|---|---|"]
        out += [f"| {n['line_id']} | {n['description_raw']} | {n['expected']} | {o['predicted']} ({o['confidence']}) | "
                f"{n['predicted']} ({n['confidence']}) |" for o, n in changed]
    return out


def case2(records: dict, ho_receipts: list[dict] | None) -> list[str]:
    if not records or not ho_receipts:
        return ["**2. (no held-out record or receipts in data_heldout/: case 2 not computed)**", ""]
    v = list(records)[-1]
    f = heldout_failures(records[v], ho_receipts)
    wrong, flips, spur = f["wrong"], f["flips"], f["spurious"]
    bands = Counter(x["confidence"] for x in wrong)
    n_lines = len(records[v]["lines"])
    cat = {x["line_id"]: x["expected"] for x in records[v]["lines"]}

    def changed(d):
        return "; ".join(f"{r}: {t}" for r, t in d.items()) or "no rule outcome changes"

    unsure = "" if bands["low"] else " without saying it is unsure"
    return [f"**2. Held-out lines the classifier gets wrong{unsure} (prompt {v}; single-annotator "
            f"labels, not dataset-scored receipts). Stage: classification.** {len(wrong)} of {n_lines} lines differ from the "
            f"annotator's category: " + "; ".join(f"{x['line_id']} {x['description_raw']!r} -> {x['predicted']}, annotator "
                                                  f"{x['expected']}" for x in wrong) + ". "
            f"{sum(x['acceptable'] for x in wrong)} of them are one of the annotator's listed alternatives, so the lenient "
            f"score counts them right. They were rated " + ", ".join(f"{b} {n}" for b, n in sorted(bands.items()))
            + f", and only `low` raises EXC-03, so the uncertainty route catches {bands['low']} of {len(wrong)}. "
            f"{len(flips)} cross the restricted boundary ({', '.join(x['line_id'] for x in flips) or 'none'}). "
            f"Fed to the engine with the annotator's recipients held fixed, the predicted categories change the rule "
            f"outcome on {len(f['by_category'])} receipt(s), compared with the annotator's categories: {changed(f['by_category'])}. "
            f"Separately, a recipient was attached to {len(spur)} line(s) that state none ("
            + ", ".join(f"{x['line_id']} {x['description_raw']!r}: {x['gift_got'][0]} {x['gift_got'][1]}" for x in spur)
            + f"); with the annotator's categories held fixed this gives: {changed(f['by_recipient'])}. "
            + ("Had the copied recipient been a government official, GIFT-04 (critical) would cite "
               + ", ".join(f"{lid} ({cat[lid]})" for lid in f["gift04_if_official"]) + ". "
               if f["gift04_if_official"] else "")
            + "Change proposed, not applied: ask the classifier for a runner-up category per line and raise EXC-03 when the "
            "top and runner-up categories disagree on `restricted`, not only when it says `low`; measure, on a fresh "
            "held-out set, how many restricted-boundary errors that catches against how many correct lines it sends to "
            "review. Score the recipient per line as its own classifier output, with lines next to a named recipient on "
            "purpose, so a recipient copied to a sibling line counts as an error.", ""]


def report(ms: dict, results: dict, extra: dict, gold: dict, receipts: list[dict], records: dict,
           ho_receipts: list[dict] | None = None) -> str:
    A, Bo, C = (ms[s] for s in SYSTEMS)
    scored = scored_ids(gold)
    want = Counter(gold[r]["labels"]["disposition"] for r in scored)
    n_lines = A["cat_acc"]["n"]
    out_ids = sorted(OUT_OF_SCOPE & gold.keys())
    desc = {li["line_id"]: li["description_raw"] for r in receipts for li in r["line_items"]}
    lang = {li["line_id"]: li["language"] for r in receipts for li in r["line_items"]}
    L = ["# Evaluation", "",
         f"Generated by `python -m validator.evaluation.evaluate` from the committed classifier cache (no model calls). "
         f"{len(scored)} scored receipts / {n_lines} scored lines ({', '.join(out_ids)} out of scope; "
         f"all {len(receipts)} run for group context). Classifier: {extra['model']}, prompt {extra['prompt_version']}. "
         f"Brackets: two-sided 95% Clopper-Pearson; `W[...]` Wilson; "
         f"`boot[...]` percentile bootstrap, {B:,} receipt resamples, seed {SEED}.", "",
         "## How to read this", "",
         f"- **Tiny n, one run.** {len(scored)} receipts, {want['pass']} pass / {want['flag']} flag / {want['review']} review. "
         "An interval spanning 30 points is the honest size of what we know. "
         f"Per-class figures on the {want['review']} review receipts are anecdotes, not rates. "
         "A bootstrap of a perfect score is degenerate (`boot[100%, 100%]`: every resample is perfect); for those, read the Clopper-Pearson bound.",
         "- **Only the classifier is measured blind.** The rule engine was written with this dataset (and its answers) in view, "
         "so B ORACLE is a consistency check of the engine against the answers, not an estimate of how it generalises. "
         "A LLM is the only number where the measured component never saw the answers (prompt = taxonomy text only), "
         "and even there the taxonomy's own examples sit in the prompt.",
         f"- **The keyword baseline (C) was frozen before scoring** (sha256 of its table and compiled patterns pinned in tests). "
         f"It feeds the same engine, so A vs C isolates the classifier; differences are measured on the same {len(scored)} receipts and are paired. "
         f"C maps descriptions to all {len(CATEGORIES)} categories (restricted words tried first), because the engine and macro F1 need a category, not just a yes/no.",
         f"- **The dataset is {'enriched' if want['flag'] / len(scored) > PREVALENCES[-1] else 'not enriched'}:** "
         f"{want['flag']}/{len(scored)} = {pct(want['flag'] / len(scored))} flag. "
         "The base-rate tables below are a what-if, not a measurement.",
         "- The held-out stress test (last section) is a separate set written by a single annotator; "
         "its expected labels are one person's judgement.", "",
         "## Headline", "",
         "| Measure | A LLM | B ORACLE | C KEYWORD |", "|---|---|---|---|"]

    def row(name: str, key: str, w: bool = False) -> None:
        L.append(f"| {name} | " + " | ".join(fmt(ms[s][key], w) for s in SYSTEMS) + " |")

    L.append("| Disposition accuracy | " + " | ".join(
        f"{fmt(ms[s]['disposition'])} boot[{pct(ms[s]['disposition_boot'][0])}, {pct(ms[s]['disposition_boot'][1])}]"
        for s in SYSTEMS) + " |")
    row(f"False positives: of {want['pass']} pass, sent to flag/review", "fp_of_pass", True)
    row(f"Missed violations: of {want['flag']} flag, passed or downgraded", "missed_of_flag", True)
    row("Exception precision (rule id)", "exc_precision")
    row("Exception recall (rule id)", "exc_recall")
    row("Evidence exact (lines), of matched exceptions", "evidence_exact")
    row("Review-signal precision", "sig_precision")
    row("Review-signal recall", "sig_recall")
    L.append("| EXC-03 signals raised (all unmatched by design) | " + " | ".join(str(ms[s]["exc03_signals"]) for s in SYSTEMS) + " |")
    L.append("| Engine errors | " + " | ".join(str(ms[s]["errors"]) for s in SYSTEMS) + " |")
    for name, key in (("Line category accuracy", "cat_acc"), ("Restricted-flag accuracy", "restricted_acc")):
        L.append(f"| {name} | {fmt(A[key])} | {n_lines}/{n_lines} (gold) | {fmt(C[key])} |")
    for name, key in (("Macro F1, categories", "macro_f1"), ("F1, restricted = true", "restricted_f1")):
        L.append(f"| {name} | " + " | ".join(
            "1.000 (gold)" if s == "B ORACLE" else f"{ms[s][key]:.3f} boot[{ms[s][key + '_boot'][0]:.3f}, {ms[s][key + '_boot'][1]:.3f}]"
            for s in SYSTEMS) + " |")
    L += ["", f"Macro F1 is the mean over the {A['n_classes']} categories present in the scored answers; a category never predicted scores 0. "
          "Restricted is looked up from the category, so its F1 only moves when a category error crosses the restricted boundary.", ""]

    # what each score says about the engine's inputs
    per_cat = Counter(x[1] for x in A["lines"])
    rare = sum(n <= 2 for n in per_cat.values())
    c_wrong = [x for x in C["lines"] if x[1] != x[2]]
    c_r_fn = sum(x[3] and not x[4] for x in C["lines"])
    c_r_fp = sum(x[4] and not x[3] for x in C["lines"])
    a_wrong = [x for x in A["lines"] if x[1] != x[2]]
    c_lines = {x[5]: x for x in C["lines"]}
    by_receipt = {r: [x for x in c_wrong if x[0] == r] for r in scored}
    c_fp = [r for r in scored if gold[r]["labels"]["disposition"] == "pass" != results["C KEYWORD"][r].disposition]
    c_missed = [r for r in scored if gold[r]["labels"]["disposition"] == "flag" != results["C KEYWORD"][r].disposition]
    b_wrong = [r for r in scored if not Bo["ok"][r]]
    disc = disposition_discordance(ms)
    better = keyword_better(A, C)

    def lines_of(rids: list[str]) -> str:
        return "; ".join(f"{r} ({', '.join(f'{desc[x[5]]!r} -> {x[2]}, correct {x[1]}' for x in by_receipt[r]) or 'every category right'})"
                         for r in rids) or "none"

    L += ["## What each score says about whether the engine gets the inputs it needs", "",
          f"- **Macro F1 on categories** (A {A['macro_f1']:.3f}, C {C['macro_f1']:.3f}). The category is the input every "
          f"category-keyed rule reads (alcohol, technology, personal, gift, health ...), so this is the most direct measure of "
          f"whether the engine is fed correctly: A gave the engine a wrong category on {len(a_wrong)} of {n_lines} lines. "
          f"Every category counts equally, and {rare} of the {A['n_classes']} categories have two lines or fewer, so one wrong "
          f"line in a rare category moves the score by up to 1/{A['n_classes']}; it measures this data, not the taxonomy.",
          f"- **F1 on restricted = true** (A {A['restricted_f1']:.3f}, C {C['restricted_f1']:.3f}). Only errors that cross the "
          f"restricted boundary count, and those decide whether a restricted-item rule can fire at all. C called {c_r_fn} "
          f"restricted line(s) unrestricted (the rule then cannot fire: a missed violation) and {c_r_fp} unrestricted line(s) "
          f"restricted (material for a false alarm). A category error inside one side of the boundary (gift vs jewelry) "
          f"leaves this score unchanged and can still change which rule fires.",
          f"- **Disposition accuracy** (A {kf(A['disposition'])}, B {kf(Bo['disposition'])}, C {kf(C['disposition'])}). "
          f"End to end: inputs and engine together. B feeds perfect categories, so every B error is an input the engine needs "
          f"beyond the category, or an engine error: B gets {', '.join(b_wrong) or 'none'} wrong (failure case 1). "
          f"A and C share the engine, so the A-C gap ({disc[0]} receipts A right and C wrong, {disc[1]} the other way) is all classifier.",
          f"- **False positives** (A {kf(A['fp_of_pass'])}, C {kf(C['fp_of_pass'])} of {want['pass']} pass). A false alarm on a "
          f"clean receipt needs a wrong input that triggers a rule. C's: {lines_of(c_fp)}. "
          f"A's {kf(A['fp_of_pass'])} has an upper bound of {pct(A['fp_of_pass']['cp'][1])}: with {want['pass']} clean receipts "
          f"this data cannot rule out roughly one false alarm in {round(1 / A['fp_of_pass']['cp'][1])} clean receipts.",
          f"- **Missed violations** (A {kf(A['missed_of_flag'])}, C {kf(C['missed_of_flag'])} of {want['flag']} flag). A miss "
          f"is an input the engine needed and did not get. C's: {lines_of(c_missed)}. "
          f"A's upper bound is {pct(A['missed_of_flag']['cp'][1])}.",
          f"- **Baseline gap.** C is wrong on {len(c_wrong)} of {n_lines} lines; on {sum(x[2] == 'other' for x in c_wrong)} "
          f"of them no keyword matched (`other`), on {sum(x[2] != 'other' for x in c_wrong)} a keyword matched something the "
          f"item is not, and {sum(lang[x[5]] != 'en' for x in c_wrong)} are non-English. "
          f"Where the keyword baseline does better than the LLM (point estimates): {', '.join(better) or 'nowhere on these measures'}. "
          f"It is free, deterministic and needs no network, which the LLM is not.", ""]

    L += ["## Disposition confusion matrices (rows = correct answer, columns = system)", ""]
    for s in SYSTEMS:
        cm = ms[s]["confusion"]
        L += [f"**{s}**", "", "| correct \\ got | flag | review | pass | total |", "|---|---|---|---|---|"]
        L += [f"| {w} | " + " | ".join(str(cm[(w, g)]) for g in DISP) + f" | {sum(cm[(w, g)] for g in DISP)} |" for w in DISP]
        L.append("")

    L += ["## Per-class precision and recall", "", "| System | Class | Precision | Recall |", "|---|---|---|---|"]
    L += [f"| {s} | {d} | {fmt(ms[s][d + '_precision'])} | {fmt(ms[s][d + '_recall'])} |" for s in SYSTEMS for d in DISP]

    L += ["", "## Per-rule exceptions (matched / raised / expected)", "", "| Rule | A LLM | B ORACLE | C KEYWORD |", "|---|---|---|---|"]
    for rule in sorted(set().union(*(ms[s]["per_rule"] for s in SYSTEMS))):
        L.append(f"| {rule} | " + " | ".join("{}/{}/{}".format(*ms[s]["per_rule"].get(rule, (0, 0, 0))) for s in SYSTEMS) + " |")
    L += ["", "Precision = matched/raised, recall = matched/expected; a rule never raised has precision n/a.", ""]

    L += ["## Where the LLM adds value over keywords (line level, paired)", ""]
    a = {x[5]: x for x in A["lines"]}
    a_only = [i for i in a if a[i][1] == a[i][2] and c_lines[i][1] != c_lines[i][2]]
    c_only = [i for i in a if a[i][1] != a[i][2] and c_lines[i][1] == c_lines[i][2]]
    both = sum(a[i][1] == a[i][2] and c_lines[i][1] == c_lines[i][2] for i in a)
    L += [f"Both right {both}, LLM only {len(a_only)}, keyword only {len(c_only)}, both wrong "
          f"{len(a) - both - len(a_only) - len(c_only)} (of {len(a)} lines).", ""]
    L += ["| Line | Description | Correct | A LLM | C KEYWORD |", "|---|---|---|---|---|"]
    L += [f"| {i} | {desc[i]} | {a[i][1]} | {a[i][2]} | {c_lines[i][2]} |" for i in sorted(a_only + c_only)]
    L.append("")
    L += [f"Disposition, paired: LLM right where keyword wrong on {disc[0]} receipts, keyword right where LLM wrong on {disc[1]}. "
          + ("Exact McNemar not run: fewer than 10 discordant receipts, so the paired difference is not testable at this n."
             if sum(disc) < 10 else f"Exact McNemar two-sided p = {mcnemar(*disc):.4f}."), ""]
    L += ["Measures where the keyword baseline beats the LLM (point estimates): " + (", ".join(better) or "none") + ".", ""]

    L += ["## LLM confidence bands (scored lines)", "", "| Band | Lines | Category correct |", "|---|---|---|"]
    for band in (*BANDS, "rule"):
        ids = [x for x in A["lines"] if extra["confidence"].get(x[5]) == band]
        if ids:
            L.append(f"| {band} | {len(ids)} | {fmt(prop(sum(x[1] == x[2] for x in ids), len(ids)))} |")
    L += ["", "`rule`: a non-itemized charge, set to `other` by rule, not by the model.", ""]

    # two failure cases
    gift = sorted(lid for lid in extra["gift_for"] if lid.rsplit("-L", 1)[0] in b_wrong)
    rec = heldout_measures(records[list(records)[-1]]) if records else None
    recipients = ", ".join(f"{lid}: {extra['gift_for'][lid][0]}" for lid in gift) or "none"
    a_bad = [r for r in scored if not A["ok"][r]]
    b_n = ("the one receipt the engine gets wrong" if len(b_wrong) == 1
           else f"the {len(b_wrong)} receipts the engine gets wrong")
    L += ["## Two failure cases", "",
          (f"A LLM gets none of the {len(scored)} scored receipts wrong, so case 1 is {b_n} "
           if not a_bad else f"A LLM gets {len(a_bad)} of the {len(scored)} scored receipts wrong ({', '.join(a_bad)}); case 1 is {b_n} ")
          + "when fed perfect categories, and case 2 comes from the held-out set, where the classifier does make errors. "
          "The keyword baseline's errors (above) belong to a system this project replaces.", "",
          f"**1. {', '.join(b_wrong) or '(none)'} under B ORACLE. Stage: classification, as the input to the rule logic.** "
          + " ".join(f"Correct {gold[r]['labels']['disposition']} with {', '.join(e['rule_id'] for e in gold[r]['labels']['expected_exceptions'])}; "
                     f"B gives {results['B ORACLE'][r].disposition} with {', '.join(fired_rules(results['B ORACLE'][r])) or 'nothing fired'}; "
                     f"A gives {results['A LLM'][r].disposition} with {', '.join(fired_rules(results['A LLM'][r])) or 'nothing fired'}."
                     for r in b_wrong)
          + (f" Every category is right in B, yet the rule cannot fire: who received the items is stated only in the line text, "
             f"and gold line labels carry the category alone. A gets it right only because the classifier also returns the stated "
             f"recipient ({recipients}). So the category is not the "
             f"whole input the engine needs, and a perfect category score would not have caught this. "
             if b_wrong and gift and all(A["ok"][r] for r in b_wrong) else
             f" B is fed every category right, so what it misses is an input beyond the category or an engine error; "
             f"stated recipients the classifier returned on these receipts: {recipients}. ")
          + (f"On the held-out set that recipient output is right in {kf(rec['Stated recipients extracted with the right kind'])} "
             f"stated cases and invented on {kf(rec['Lines with no stated recipient given one anyway'])} lines with none stated. "
             if rec else "")
          + "Change: treat the recipient as a scored classifier output with its own test set, and take it from a structured "
          "field at submission when one exists, so an anti-corruption exception never rests on one free-text reading.", ""]
    stretch = {sy: oracle.compare(results[sy], gold, stretch=True) for sy in SYSTEMS}
    L += case2(records, ho_receipts)

    L += [f"## Stretch: out-of-scope receipts ({', '.join(out_ids)}; not scored, not in any figure above)", "",
          "| Receipt | Correct | " + " | ".join(SYSTEMS) + " |", "|---|---|" + "---|" * len(SYSTEMS)]
    for r in out_ids:
        lab = gold[r]["labels"]
        want_rules = [x["rule_id"] for x in lab["expected_exceptions"] + lab["review_signals"]]
        L.append(f"| {r} | {lab['disposition']}: {', '.join(want_rules) or '-'} | " + " | ".join(
            f"{results[sy][r].disposition}: {', '.join(fired_rules(results[sy][r])) or '-'}" for sy in SYSTEMS) + " |")
    L += ["", "Differences from the answer key, matched as for the scored receipts (rule id, exact line ids, review "
          "signals, disposition): " + "; ".join(f"{sy} {len(stretch[sy])}" for sy in SYSTEMS) + "."]
    L += [f"- {sy}: {r} {what}: expected {want}, got {got}" for sy in SYSTEMS for r, what, want, got in stretch[sy]]
    dated = sum(bool(r.get("trip_start") and r.get("trip_end")) for r in receipts)
    L += ["", "TIME-04 never applies on this data: trip records hold no start or end dates." if not dated
          else f"TIME-04 can apply to the {dated} receipt(s) whose trip records hold start and end dates.", ""]

    L += ["## Base rate: what if violations were rare (what-if, not measured)", ""]
    sf, pf = A["sens_flag"], A["spec_flag"]
    lows = [pct(ppv(sf["cp"][0], pf["cp"][0], p)) for p in PREVALENCES]
    last = records[list(records)[-1]] if records else None
    cost = (f" (the last held-out run cost ${last['meta']['cost_usd'] / len({x['receipt'] for x in last['lines']}):.5f} per receipt)"
            if last else "")
    L += [f"This dataset is {pct(want['flag'] / len(scored))} flag; a real expense stream has a few percent. "
          f"{pf['n'] - pf['k']} false flag(s) among {pf['n']} non-flag receipts is compatible with a false-alarm rate of up to "
          f"{pct(1 - pf['cp'][0])}; with sensitivity and specificity both at their lower bounds, the share of A's flags that are real (PPV) at "
          f"{', '.join(pct(p) for p in PREVALENCES)} prevalence falls to {', '.join(lows)}: the false-positive numbers above "
          f"say little about what reviewers would see. The keyword baseline's measured specificity "
          f"({pct(C['spec_flag']['p'])}) already gives a point PPV of {pct(ppv(C['sens_flag']['p'], C['spec_flag']['p'], PREVALENCES[1]))} at "
          f"{pct(PREVALENCES[1])}. Before production I would measure per-rule precision on a random, not enriched, sample "
          f"of real receipts checked by auditors, the review-queue workload (flag + review per 1,000 receipts), drift in "
          f"the classifier's confidence bands and category mix over time, and cost per receipt{cost}.", "",
          "PPV = sens·p / (sens·p + (1−spec)(1−p)). Sensitivity and specificity are the measured ones below; "
          "the PPV range plugs in both lower CP bounds and both upper CP bounds (PPV rises in both). "
          "A specificity of 100% means no false alarm was *observed* among few negatives, not that there are none; "
          "the lower bound is what to plan with.", ""]
    for label, sk, pk in ((f"Alarm = `flag`; condition = correct answer is flag (negatives: {want['pass']} pass + {want['review']} review)",
                           "sens_flag", "spec_flag"),
                          (f"Alarm = `flag` or `review` (a human looks); condition = correct answer is not pass (negatives: {want['pass']} pass)",
                           "sens_any", "spec_any")):
        L += [f"**{label}**", "", "| System | Sensitivity | Specificity | " + " | ".join(f"PPV at {pct(p)}" for p in PREVALENCES) + " |",
              "|---|---|---|" + "---|" * len(PREVALENCES)]
        for s in SYSTEMS:
            se, sp = ms[s][sk], ms[s][pk]
            cells = [f"{pct(ppv(se['p'], sp['p'], p))} [{pct(ppv(se['cp'][0], sp['cp'][0], p))}, {pct(ppv(se['cp'][1], sp['cp'][1], p))}]"
                     for p in PREVALENCES]
            L.append(f"| {s} | {fmt(se)} | {fmt(sp)} | " + " | ".join(cells) + " |")
        L.append("")

    perfect = not a_wrong and not a_bad
    L += ["## What a score of 1.000 does and does not mean" if perfect else "## What A's scores do and do not mean", "",
          f"A's macro F1 of {A['macro_f1']:.3f} and {kf(A['disposition'])} dispositions mean that, in this one run, the "
          + (f"classifier gave the engine the category it needed on all {n_lines} scored lines and the engine turned them into "
             f"the right answer. They do not mean the system is always right. " if perfect else
             f"classifier gave the engine a wrong category on {len(a_wrong)} of {n_lines} scored lines and the system got "
             f"{len(a_bad)} of {len(scored)} dispositions wrong. ")
          + f"The engine was written with these "
          f"receipts and their answers in view, so its share of the score is consistency with the answers, not generalisation; "
          f"the classifier is the only blind component, and its prompt holds the taxonomy's own examples. It is one run of a "
          f"sampled model, on n = {len(scored)} receipts: the 95% lower bounds are {pct(A['disposition']['cp'][0])} for "
          f"dispositions and {pct(A['cat_acc']['cp'][0])} for line categories. The held-out set is the better estimate of the "
          + (f"classifier: {fmt(rec['Exact category, all lines'])} exact there." if rec else "classifier."), ""]

    L += ["## Held-out stress test (classifier only; summarised from data_heldout/, not rerun)", ""]
    L += heldout_section(records)
    return "\n".join(L) + "\n"


def load_records() -> dict:
    return {v: json.loads(p.read_text(encoding="utf-8")) for v, p in HELDOUT.items() if p.exists()}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--allow-calls", action="store_true", help="allow paid classifier calls on a cache miss")
    args = ap.parse_args(argv)
    results, cats, extra, gold, receipts = run_systems(args.allow_calls)
    ms = {s: measures(results[s], cats[s], gold) for s in SYSTEMS}
    OUT.parent.mkdir(exist_ok=True)
    ho = load_receipts(HELDOUT_INPUT) if HELDOUT_INPUT.exists() else None
    OUT.write_text(report(ms, results, extra, gold, receipts, load_records(), ho), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
