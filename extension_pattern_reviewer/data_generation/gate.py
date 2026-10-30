"""Anti-shortcut gate: can SURFACE features (no meaning) predict the label? If AUROC > 0.60 the dataset has a shortcut and must be resampled.
Features are computed from the rendered history text, so it works for old (train.jsonl) and new (v2) data alike. Pure Python."""
import re, math, json, random, collections, statistics
LINE = re.compile(r"^- (\S+-R\d+) \| (\d{4}-\d{2}-(\d{2})) (\d{2}):(\d{2}) \((\w{3})\) \| (.*?) \| (.*?) \| \$([\d,]+\.\d\d)(.*?) \| (.*)$")
TYPES = ["Client Entertainment", "Client Gifts", "Computer Equipment", "Lodging", "Meals - Individual", "Meals - Team", "Office Supplies", "Travel - Other"]
def features(text):
    rows = [LINE.match(l) for l in text.split("\n")]; rows = [m for m in rows if m]
    if not rows: return None
    n = len(rows); amts = [float(m.group(9).replace(",", "")) for m in rows]; wk = sum(m.group(6) in ("Sat", "Sun") for m in rows)
    days = sorted(int(m.group(3)) for m in rows); gaps = [b - a for a, b in zip(days, days[1:])] or [0]
    merch = collections.Counter(m.group(7) for m in rows); trips = {t for t in re.findall(r"TRIP-\d+", text)}
    f = {"n_receipts": n, "weekend_count": wk, "weekend_frac": wk / n, "n_trips": len(trips), "mean_amount": statistics.mean(amts), "std_amount": statistics.pstdev(amts), "total": sum(amts), "round_frac": sum(a == int(a) for a in amts) / n,
         "attendee_frac": sum("attendees" in m.group(10) for m in rows) / n, "max_same_merchant": max(merch.values()), "distinct_merchants": len(merch), "mean_gap": statistics.mean(gaps), "max_gap": max(gaps), "text_len": len(text),
         "nonascii_frac": sum(ord(c) > 127 for c in text) / max(1, len(text)), "late_hour_frac": sum(int(m.group(4)) >= 21 for m in rows) / n, "month": int(rows[0].group(2)[5:7])}
    for t in TYPES: f["share_" + t.split(" ")[0] + t.split(" ")[-1][:3]] = sum(m.group(8) == t for m in rows) / n
    return f
def auroc(scores, labels):
    pos = [s for s, y in zip(scores, labels) if y]; neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg: return float("nan")
    order = sorted(range(len(scores)), key=lambda i: scores[i]); ranks = [0] * len(scores); i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]: j += 1
        for k in range(i, j + 1): ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    rp = sum(ranks[i] for i in range(len(scores)) if labels[i]); return (rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))
def logistic_cv(X, y, folds=5, seed=0, epochs=300, lr=.1, l2=.05):
    n = len(X); d = len(X[0]); mu = [statistics.mean(r[j] for r in X) for j in range(d)]; sd = [statistics.pstdev([r[j] for r in X]) or 1 for j in range(d)]
    Z = [[(r[j] - mu[j]) / sd[j] for j in range(d)] for r in X]; idx = list(range(n)); random.Random(seed).shuffle(idx); out = [0.0] * n
    for f in range(folds):
        te = set(idx[f::folds]); tr = [i for i in idx if i not in te]; w = [0.0] * d; b = 0.0
        for _ in range(epochs):
            gw = [0.0] * d; gb = 0.0
            for i in tr:
                z = b + sum(w[j] * Z[i][j] for j in range(d)); p = 1 / (1 + math.exp(-max(-30, min(30, z)))); e = p - y[i]
                for j in range(d): gw[j] += e * Z[i][j]
                gb += e
            for j in range(d): w[j] -= lr * (gw[j] / len(tr) + l2 * w[j])
            b -= lr * gb / len(tr)
        for i in te: out[i] = b + sum(w[j] * Z[i][j] for j in range(d))
    return auroc(out, y)
def report(texts, labels, name=""):
    F = [features(t) for t in texts]; keep = [i for i, f in enumerate(F) if f]; F = [F[i] for i in keep]; y = [labels[i] for i in keep]; names = list(F[0])
    uni = sorted(((abs(auroc([f[k] for f in F], y) - .5) + .5, k, auroc([f[k] for f in F], y)) for k in names), reverse=True)
    cv = logistic_cv([[f[k] for k in names] for f in F], y)
    print(f"[{name}] n={len(F)} (fraud={sum(y)}, clean={len(y) - sum(y)})  surface-feature logistic AUROC (5-fold) = {cv:.3f}   gate: <= 0.60 -> {'PASS' if cv <= .60 else 'FAIL (shortcut present)'}")
    print("   top single features:", ", ".join(f"{k} {a:.2f}" for _, k, a in uni[:5]))
    return cv
if __name__ == "__main__":
    import sys
    P = "/Users/geboou/Desktop/oversight/finetune/data_synth/reviewer_sft/train.jsonl"; T = []; Y = []
    for l in open(P):
        x = json.loads(l); u = x["messages"][1]["content"]; a = json.loads(x["messages"][2]["content"]); T.append(u); Y.append(1 if a["escalate"] else 0)
    report(T, Y, "v1 training set (810)")
