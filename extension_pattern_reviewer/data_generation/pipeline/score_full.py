"""the reference company-style scoring of reviewers on the 275 eval histories (receipt level + dollar-weighted).
Usage: python3 score_full.py   (loads tuned from ../results/reviewer_ft.json, haiku/sonnet from review_out/)
Receipt-level: positive = planted receipt; predicted = escalated receipt. Precision/recall/F1 pooled over E1+E2+E3
(histories with fraud) plus E4 (clean: every escalation is a false positive). Dollar-weighted recall = sum($ planted caught)/sum($ planted).
Also reports history-level recall (>=1 planted receipt escalated) with Wilson CI and clean-history false-alarm rate."""
import json, re, glob, math, collections
D = "/Users/geboou/Desktop/oversight/finetune/data_synth/"
key = json.load(open(D + "reviewer_sft/eval_key.json"))
inp = json.load(open(D + "reviewer_sft/eval_inputs.json"))
amt = {}
for h in inp:
    for m in re.finditer(r"^- (\S+-R\d+) \|[^|]*\|[^|]*\|[^|]*\| \$([\d,]+\.\d\d)", h["text"], re.M): amt[m.group(1)] = float(m.group(2).replace(",", ""))
def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return round(100 * (c - m) / d), round(100 * (c + m) / d)
def load_files(model):
    pred = {}
    for f in glob.glob(D + f"review_out/{model}_*.json"):
        for h in json.load(open(f)):
            if h["history_id"] in key: pred[h["history_id"]] = {e["receipt_id"] for e in h.get("escalate", [])}
    return pred
def load_tuned(p):
    r = json.load(open(p)); return {h: set(v["escalate"]) for h, v in r.items()}
def score(name, pred, kinds=("E1_heldout_schemes", "E2_unseen_families", "E3_seen_families")):
    tp = fp = fn = 0; dtp = dall = 0.0; hd = hn = 0; fa = cn = 0; fp_clean = 0
    for hid, k in key.items():
        if hid not in pred: continue
        esc = pred[hid]; pl = set(k["planted"])
        if k["kind"] == "E4_clean_control": cn += 1; fa += bool(esc); fp_clean += len(esc); continue
        if k["kind"] not in kinds: continue
        hn += 1; hd += bool(pl & esc); tp += len(pl & esc); fn += len(pl - esc); fp += len(esc - pl)
        dtp += sum(amt.get(r, 0) for r in pl & esc); dall += sum(amt.get(r, 0) for r in pl)
    fpt = fp + fp_clean
    pr = tp / max(1, tp + fpt); rc = tp / max(1, tp + fn); f1 = 2 * pr * rc / max(1e-9, pr + rc)
    print(f"{name:8s} n={len(pred):3d} | history recall {hd}/{hn} = {100*hd/max(1,hn):.0f}% CI{wilson(hd,hn)} | clean false alarms {fa}/{cn} = {100*fa/max(1,cn):.0f}% CI{wilson(fa,cn)} | receipts P {100*pr:.0f}% R {100*rc:.0f}% F1 {100*f1:.0f}% | $-weighted recall {100*dtp/max(1,dall):.0f}%")
for kinds, lab in [(("E1_heldout_schemes", "E2_unseen_families"), "E1+E2 (unseen)"), (("E3_seen_families",), "E3 (seen)")]:
    print("==", lab)
    for name, pred in [("tuned", load_tuned(D + "../results/reviewer_ft.json")), ("haiku", load_files("haiku")), ("sonnet", load_files("sonnet"))]:
        if pred: score(name, pred, kinds)
