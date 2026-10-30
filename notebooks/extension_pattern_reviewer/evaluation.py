"""evaluation: the deterministic score of the pattern reviewer. No LLM judge, no opinion: just counting.
A fraud history is "detected" if the reviewer escalates >=1 planted receipt. A clean history is a "false alarm" if it escalates anything."""
import json, math, random
from pathlib import Path
DATA = Path(__file__).resolve().parent / "data"


def load(): return json.load(open(DATA / "predictions.json"))


def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return round(100 * (c - m) / d), round(100 * (c + m) / d)


def metrics(key, amt, pred, fraud_kinds, clean_kind):
    fr = [h for h, k in key.items() if k["kind"] in fraud_kinds and h in pred]; cl = [h for h, k in key.items() if k["kind"] == clean_kind and h in pred]
    P = {h: set(v) for h, v in pred.items()}
    det = sum(bool(set(key[h]["planted"]) & P[h]) for h in fr)
    caught = sum(sum(amt.get(r, 0) for r in set(key[h]["planted"]) & P[h]) for h in fr); total = sum(sum(amt.get(r, 0) for r in key[h]["planted"]) for h in fr)
    fa = sum(bool(P[h]) for h in cl)
    tp = sum(len(set(key[h]["planted"]) & P[h]) for h in fr); fp = sum(len(P[h] - set(key[h]["planted"])) for h in fr) + sum(len(P[h]) for h in cl); fn = sum(len(set(key[h]["planted"]) - P[h]) for h in fr)
    pr = tp / max(1, tp + fp); rc = tp / max(1, tp + fn)
    return {"n_fraud": len(fr), "n_clean": len(cl), "recall": det / max(1, len(fr)), "recall_ci": wilson(det, len(fr)), "recall_usd": caught / max(1, total), "false_alarms": fa / max(1, len(cl)), "fa_ci": wilson(fa, len(cl)),
            "receipt_precision": pr, "receipt_recall": rc, "receipt_f1": 2 * pr * rc / max(1e-9, pr + rc), "escalates_on_fraud": sum(bool(P[h]) for h in fr) / max(1, len(fr)), "escalates_on_clean": fa / max(1, len(cl))}


def bootstrap_diff(key, amt, a, b, fraud_kinds, n=10000, seed=7):
    """CLUSTER bootstrap (two stages): resample SCHEMES with replacement, then histories inside each chosen scheme.
    Returns the 95% CI of (a - b) for history recall and for dollar recall. Wider (more honest) than resampling histories alone."""
    fr = [h for h, k in key.items() if k["kind"] in fraud_kinds]; groups = {}
    for h in fr: groups.setdefault(key[h]["family"], []).append(h)
    fams = list(groups); A = {h: set(v) for h, v in a.items()}; Bb = {h: set(v) for h, v in b.items()}; rnd = random.Random(seed); dh = []; dd = []
    def st(P, s):
        return sum(bool(set(key[h]["planted"]) & P[h]) for h in s), sum(sum(amt.get(r, 0) for r in set(key[h]["planted"]) & P[h]) for h in s), sum(sum(amt.get(r, 0) for r in key[h]["planted"]) for h in s)
    for _ in range(n):
        s = []
        for f in (rnd.choice(fams) for _ in fams): s += [rnd.choice(groups[f]) for _ in groups[f]]
        ha, da_, dall = st(A, s); hb, db, _ = st(Bb, s); dh.append((ha - hb) / len(s)); dd.append((da_ - db) / max(1, dall))
    q = lambda x, p: sorted(x)[int(p * n)]
    return (q(dh, .025), q(dh, .975)), (q(dd, .025), q(dd, .975))
