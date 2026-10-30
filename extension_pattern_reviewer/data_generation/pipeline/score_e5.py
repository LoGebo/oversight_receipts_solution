"""Score E5 (independent set) with the PRE-REGISTERED criteria (FINETUNE_LOG §13). Usage: python3 score_e5.py [results_dir]
Comparator = best frontier configuration (A, B, C zero-shot, fs few-shot) by history recall. Paired bootstrap over histories, 10,000 resamples, seed 7."""
import json, re, glob, math, random, sys, collections
D = "/Users/geboou/Desktop/oversight/finetune/data_synth/"
key = json.load(open(D + "reviewer_sft/eval5_key.json")); inp = json.load(open(D + "reviewer_sft/eval5_inputs.json"))
amt = {}
for h in inp:
    for m in re.finditer(r"^- (\S+-R\d+) \|[^|]*\|[^|]*\|[^|]*\| \$([\d,]+\.\d\d)", h["text"], re.M): amt[m.group(1)] = float(m.group(2).replace(",", ""))
def files(model):
    p = {}
    for f in glob.glob(D + f"review_out/{model}_xv*.json"):
        for h in json.load(open(f)):
            if h["history_id"] in key: p[h["history_id"]] = {e["receipt_id"] for e in h.get("escalate", [])}
    return p
def tuned():
    try: return {h: set(v["escalate"]) for h, v in json.load(open(D + "../results/reviewer_e5ft.json")).items()}
    except Exception: return {}
FR = [h for h, k in key.items() if k["kind"] == "E5_independent"]; CL = [h for h, k in key.items() if k["kind"] == "E5_clean"]
def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return round(100 * (c - m) / d), round(100 * (c + m) / d)
def stats(p, hs):
    hd = sum(bool(set(key[h]["planted"]) & p[h]) for h in hs)
    dt = sum(sum(amt.get(r, 0) for r in set(key[h]["planted"]) & p[h]) for h in hs); da = sum(sum(amt.get(r, 0) for r in key[h]["planted"]) for h in hs)
    return hd, dt, da
def full(name, p):
    if not all(h in p for h in key): print(f"{name}: incomplete ({len(p)}/{len(key)})"); return None
    hd, dt, da = stats(p, FR); fa = sum(bool(p[h]) for h in CL)
    tp = sum(len(set(key[h]["planted"]) & p[h]) for h in FR); fp = sum(len(p[h] - set(key[h]["planted"])) for h in FR) + sum(len(p[h]) for h in CL); fn = sum(len(set(key[h]["planted"]) - p[h]) for h in FR)
    pr = tp / max(1, tp + fp); rc = tp / max(1, tp + fn); f1 = 2 * pr * rc / max(1e-9, pr + rc)
    print(f"{name:12s} recall hist {hd}/{len(FR)} = {100*hd/len(FR):.0f}% CI{wilson(hd,len(FR))} | $-recall {100*dt/da:.0f}% | FA {fa}/{len(CL)} = {100*fa/len(CL):.0f}% CI{wilson(fa,len(CL))} | receipts P {100*pr:.0f} R {100*rc:.0f} F1 {100*f1:.0f}")
    return {"rec": hd / len(FR), "fa": fa / len(CL)}
def boot(a, b, n=10000):
    rnd = random.Random(7); d_h = []; d_d = []
    for _ in range(n):
        s = [rnd.choice(FR) for _ in FR]
        ha, da_, daa = stats(a, s); hb, db, dbb = stats(b, s)
        d_h.append((ha - hb) / len(s)); d_d.append(da_ / max(1, daa) - db / max(1, dbb))
    lo = lambda x: sorted(x)[int(.025 * n)]; hi = lambda x: sorted(x)[int(.975 * n)]
    return (lo(d_h), hi(d_h)), (lo(d_d), hi(d_d))
def api(tag):
    try: return {h: set(v["escalate"]) for h, v in json.load(open(D + f"../results/api_{tag}.json")).items()}
    except Exception: return {}
P = {"opus45zero": api("opus45zero"), "opus45fs": api("opus45fs"), "sonnet55api": api("sonnet55api"), "tuned": tuned(), "sonnetA": files("sonnetA"), "sonnetB": files("sonnetB"), "sonnetC": files("sonnetC"), "sonnetfs": files("sonnetfs"), "haikux": files("haikux")}
R = {k: full(k, v) for k, v in P.items() if v}
sons = [k for k in ("sonnetA", "sonnetB", "sonnetC", "sonnetfs", "sonnet55api", "opus45zero", "opus45fs") if R.get(k)]
if R.get("tuned") and sons:
    best = max(sons, key=lambda k: R[k]["rec"]); print("best frontier config by history recall:", best)
    u = {h: P["tuned"][h] | P[best][h] for h in key}; full("union", u)
    (hl, hh), (dl, dh) = boot(P["tuned"], P[best]); fa_t, fa_s = R["tuned"]["fa"], R[best]["fa"]
    print(f"paired bootstrap tuned - {best}: history recall diff CI95 [{100*hl:.1f}, {100*hh:.1f}] pts; $-recall diff CI95 [{100*dl:.1f}, {100*dh:.1f}] pts; FA tuned {100*fa_t:.0f}% vs {100*fa_s:.0f}%")
    wins = hl > 0 and dl > 0 and fa_t <= .05 and fa_t <= fa_s
    ties = hl <= 0 <= hh and fa_t <= fa_s
    print("VERDICT:", "GANA" if wins else ("EMPATA" if ties else "PIERDE"), "(criterios pre-registrados FINETUNE_LOG §13)")
