"""Build catalog_patterns.json: every fraud pattern an LLM (or the code families) produced, with its role, and one example history rendered with the planted receipts marked."""
import json, glob, collections, sys
sys.path.insert(0, "/Users/geboou/Desktop/oversight/finetune/data_synth/pipeline")
from render_history import render
D = "/Users/geboou/Desktop/oversight/finetune/data_synth/"
held = set(json.load(open(D + "reviewer_sft/heldout_schemes.json")))
FAM_SEEN = ["gift_splitting", "gift_under_naming", "tech_just_under", "itemize_just_under", "meal_cap_hugging"]; FAM_UNSEEN = ["meal_just_under_doc", "duplicate_submission", "pa_reuse"]
def load(pat):
    o = []
    for f in sorted(glob.glob(D + pat)): o += json.load(open(f))
    return o
def example(h):
    hid = "EJ"; text, ids = render(hid, h); pl = set(h["planted_receipts"] if "planted_receipts" in h else [r["receipt_id"] for r in h["receipts"] if r.get("planted")])
    plids = {ids[r] for r in pl if r in ids}
    lines = [(l + "   ◄ PLANTED") if any(l.startswith(f"- {p} ") for p in plids) else l for l in text.split("\n")]
    rec = sorted([r for r in h["receipts"] if r["receipt_id"] in pl], key=lambda r: r["transaction_datetime"])
    ex = [f"{r['transaction_datetime'][:10]} · {r['merchant_name']} · ${r['total_amount_usd']:.2f} · " + " + ".join(li["description_raw"] for li in r["line_items"])[:70] for r in rec[:3]]
    return "\n".join(lines), ex, len(pl)
cat = []
def add(origen, scheme, reason, hs, role):
    t, ex, _ = example(hs[0]); npl = [len(h["planted_receipts"]) if "planted_receipts" in h else sum(bool(r.get("planted")) for r in h["receipts"]) for h in hs]
    cat.append({"origin": origen, "scheme": scheme, "reason": reason, "source_histories": len(hs), "planted_avg": round(sum(npl) / len(npl), 1), "role": role, "example_receipts": ex, "example_history": t, "engine": "all pass"})
fam = collections.defaultdict(list)
for f in ("patterns_v3_train.jsonl", "patterns_v3_test_seen.jsonl", "patterns_v3_test_unseen.jsonl"):
    for l in open(D + f):
        h = json.loads(l)
        if h["family"] != "clean": fam[h["family"]].append(h)
for k in FAM_SEEN: add("Base family (defined in code)", k, fam[k][0]["reason"], fam[k], "Training and E3 test (seen)")
for k in FAM_UNSEEN: add("Base family (defined in code)", k, fam[k][0]["reason"], fam[k], "E2 test (unseen family)")
for name, pat, org in [("r1", "redteam/rt_*.ok.json", "Red team round 1 (Claude agents)"), ("r2", "redteam/rt2_*.ok.json", "Red team round 2 (Claude agents)")]:
    by = collections.OrderedDict()
    for h in load(pat): by.setdefault(h["scheme"], []).append(h)
    for k, hs in by.items(): add(org, k, hs[0]["reason"], hs, "E1 test (held-out scheme)" if k in held else "Training")
by = collections.OrderedDict()
for h in load("redteam/e5/e5_[0-9][0-9].ok.json"): by.setdefault(h["scheme"], []).append(h)
for k, hs in by.items(): add("E5 independent (Opus agents, blind)", k, hs[0]["reason"], hs, "Final E5 test (never trained on)")
json.dump(cat, open(D + "catalog_patterns.json", "w"), ensure_ascii=False, indent=1)
print(len(cat), collections.Counter(c["role"] for c in cat))
