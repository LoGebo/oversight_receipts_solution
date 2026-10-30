"""Build blind reviewer inputs. Code computes the summaries (like the reference company: the LLM does not calculate them). Receipt ids are renamed so nothing leaks the source set."""
import json, random, collections
from pathlib import Path
D = Path("/Users/geboou/Desktop/oversight/finetune/data_synth")
rng = random.Random(9191)
def load(sp): return [json.loads(x) for x in open(D / f"patterns_v2_{sp}.jsonl")]
CONTROL = [json.loads(x) for x in open(D / "patterns_v3_control2.jsonl")]
items = [(h, "control2_clean") for h in rng.sample(CONTROL, 91)]
rng.shuffle(items)
def desc(r): return " + ".join(f"{li['description_raw']} (x{li['quantity']})" if li["quantity"] > 1 else li["description_raw"] for li in r["line_items"])
def render(hid, h):
    recs = sorted(h["receipts"], key=lambda r: r["transaction_datetime"]); ids = {r["receipt_id"]: f"{hid}-R{i+1:02d}" for i, r in enumerate(recs)}
    L = [f"EMPLOYEE HISTORY {hid} (entity {recs[0]['entity']}, all amounts in USD). Every receipt below was ALREADY checked by the deterministic engine and got verdict `pass`.", "", "RECEIPTS (chronological):"]
    for r in recs:
        att = f", {r['attendee_count']} attendees" if r["attendee_count"] else ""; tr = f", {r['trip_id']} ({r['trip_nights']} nights)" if r["trip_id"] else ""
        pa = f", approval {r['pre_approval_ref']}" if r["pre_approval_ref"] else ""; it = "" if r["itemized"] else ", NOT itemized"
        L.append(f"- {ids[r['receipt_id']]} | {r['transaction_datetime'].replace('T', ' ')[:16]} ({['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][__import__('datetime').datetime.fromisoformat(r['transaction_datetime']).weekday()]}) | {r['merchant_name']} | {r['submitted_expense_type']} | ${r['total_amount_usd']:.2f}{att}{tr}{pa}{it} | {desc(r)}")
    mer = collections.defaultdict(lambda: [0, 0.0])
    for r in recs: mer[r["merchant_name"]][0] += 1; mer[r["merchant_name"]][1] += r["total_amount_usd"]
    typ = collections.defaultdict(list)
    for r in recs: typ[r["submitted_expense_type"]].append(r["total_amount_usd"])
    L += ["", "SUMMARIES (computed by code):", f"- total claimed: ${sum(r['total_amount_usd'] for r in recs):.2f} in {len(recs)} receipts"]
    L.append("- by expense type: " + "; ".join(f"{k}: {len(v)} receipts, total ${sum(v):.2f}, amounts {sorted(v)}" for k, v in typ.items()))
    L.append("- merchants used more than once: " + ("; ".join(f"{k}: {v[0]} times, ${v[1]:.2f}" for k, v in mer.items() if v[0] > 1) or "none"))
    wk = [ids[r["receipt_id"]] for r in recs if __import__("datetime").datetime.fromisoformat(r["transaction_datetime"]).weekday() >= 5]
    L.append("- receipts dated Saturday or Sunday: " + (", ".join(wk) or "none"))
    tr = collections.defaultdict(list)
    for r in recs:
        if r["trip_id"]: tr[r["trip_id"]].append(r)
    L.append("- trips: " + ("; ".join(f"{k}: declared {v[0]['trip_nights']} nights, {len(v)} receipts dated {min(x['transaction_datetime'][:10] for x in v)} to {max(x['transaction_datetime'][:10] for x in v)}" for k, v in tr.items()) or "none"))
    pa = collections.Counter(r["pre_approval_ref"] for r in recs if r["pre_approval_ref"])
    L.append("- approval references used: " + (", ".join(f"{k} x{v}" for k, v in pa.items()) or "none"))
    return "\n".join(L), ids
key = {}; chunks = []; cur = []
for i, (h, kind) in enumerate(items):
    hid = f"K{i+1:03d}"; text, ids = render(hid, h)
    key[hid] = {"kind": kind, "family": h["family"], "planted": [ids[r] for r in h["planted_receipts"]], "all_receipts": list(ids.values())}
    cur.append({"history_id": hid, "text": text})
    if len(cur) == 13: chunks.append(cur); cur = []
if cur: chunks.append(cur)
for n, c in enumerate(chunks, 1): json.dump(c, open(D / "review_in" / f"rv{n+40:02d}.json", "w"), ensure_ascii=False, indent=1)
json.dump(key, open(D / "review_key_v3b.json", "w"), ensure_ascii=False)
print("histories", len(items), "chunks", len(chunks), dict(collections.Counter(v["kind"] for v in key.values())))
