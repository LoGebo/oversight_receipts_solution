"""Build the reviewer SFT set + the held-out evaluation sets (E1-E4). Run with plain python3."""
import json, random, sys, collections
from pathlib import Path
D = Path("/Users/geboou/Desktop/oversight/finetune/data_synth"); sys.path.insert(0, str(D / "pipeline"))
import render_history as RH
rng = random.Random(2026)
def load(p): return [json.loads(x) for x in open(D / p)] if (D / p).exists() else []
V3T, V3S, V3U, CTRL, CTRL2 = [h for h in load("patterns_v3_train.jsonl") if int(h["history_id"][2:]) > 10130], load("patterns_v3_test_seen.jsonl"), load("patterns_v3_test_unseen.jsonl"), load("patterns_v3_control.jsonl"), load("patterns_v3_control2.jsonl")
RT = load("patterns_v2_redteam.jsonl") + load("patterns_v2_redteam2.jsonl")
schemes = sorted({h["scheme"] for h in RT}); hold = set(rng.sample(schemes, min(12, len(schemes) // 4)))
SYSTEM = open(D / "review_in" / "REVIEWER_TASK.md").read()
SYSTEM = ("You are the second-line reviewer of an expense-policy engine. You receive one employee's month of receipts; the deterministic engine already passed each receipt on its own. "
          "Find PATTERNS ACROSS RECEIPTS that suggest circumventing a limit, double-claiming, claims that do not fit the trip, relationship, headcount or items, or hidden personal spending. "
          "You may only ESCALATE receipts to a human; you never reject. Stay quiet (empty list) when the history looks ordinary.\n"
          "Policy digest: gift to a client at most $50 per named recipient per receipt, gifts of $10 or more must name the recipient; computer accessories at most $200 per item unless a pre-approval (PA-...) is attached; receipts above $75 must be itemized; "
          "meals per person per day at most $75 (APAC $60), team meals above $150 need attendees documented; individual meals, lodging and other travel belong to a trip; OTC health items at most $25 per trip.\n"
          'Answer only with JSON: {"escalate":[{"receipt_id":"...","reason":"<one sentence>"}]}')
def example(h, hid):
    text, ids = RH.render(hid, h); pl = [ids[r] for r in h["planted_receipts"]]
    reason = h.get("reason") or "Suspicious pattern across receipts."
    ans = {"escalate": [{"receipt_id": r, "reason": reason} for r in sorted(pl)]}
    return text, pl, json.dumps(ans, ensure_ascii=False, separators=(",", ":"))
def chat(text, ans): return {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}, {"role": "assistant", "content": ans}]}
fam = collections.defaultdict(list)
for h in V3T: fam[h["family"]].append(h)
train_h = []
for f, hs in fam.items():
    train_h += rng.sample(hs, min(len(hs), 300 if f == "clean" else 40))
train_h += [h for h in RT if h["scheme"] not in hold]
train_h += rng.sample(CTRL, min(len(CTRL), 100))
rng.shuffle(train_h)
rows = []
for i, h in enumerate(train_h):
    t, pl, a = example(h, f"T{i+1:04d}"); rows.append(chat(t, a))
nval = max(20, len(rows) // 20); val, tr = rows[:nval], rows[nval:]
(D / "reviewer_sft").mkdir(exist_ok=True)
for name, rs in (("train", tr), ("valid", val)):
    open(D / "reviewer_sft" / f"{name}.jsonl", "w").write("\n".join(json.dumps(r, ensure_ascii=False) for r in rs) + "\n")
# held-out eval sets
ev = []; key = {}
def add(kind, hs):
    for h in hs:
        hid = f"E{len(ev)+1:04d}"; t, pl, a = example(h, hid)
        ev.append({"history_id": hid, "text": t}); key[hid] = {"kind": kind, "family": h.get("scheme") or h["family"], "planted": pl, "all": []}
add("E1_heldout_schemes", [h for h in RT if h["scheme"] in hold])
add("E2_unseen_families", rng.sample([h for h in V3U if h["family"] != "clean"], 60))
add("E3_seen_families", rng.sample([h for h in V3S if h["family"] != "clean"], 40))
import glob
k2 = json.load(open(D / "review_key_v3b.json"))
for f in sorted(glob.glob(str(D / "review_in" / "rv4[1-7].json"))):
    for h in json.load(open(f)):
        hid = f"E{len(ev)+1:04d}"; ev.append({"history_id": hid, "text": h["text"].replace(h["history_id"], hid)})
        key[hid] = {"kind": "E4_clean_control", "family": "clean", "planted": [], "all": [], "src_id": h["history_id"]}
rng.shuffle(ev)
json.dump(ev, open(D / "reviewer_sft" / "eval_inputs.json", "w"), ensure_ascii=False); json.dump(key, open(D / "reviewer_sft" / "eval_key.json", "w"), ensure_ascii=False)
json.dump(sorted(hold), open(D / "reviewer_sft" / "heldout_schemes.json", "w"))
print("train", len(tr), "valid", len(val), "| eval", dict(collections.Counter(v["kind"] for v in key.values())), "| held-out schemes", len(hold), "of", len(schemes))
print("positives in train:", sum(1 for r in tr if '"escalate":[{' in r["messages"][2]["content"]), "clean:", sum(1 for r in tr if r["messages"][2]["content"] == '{"escalate":[]}'))
