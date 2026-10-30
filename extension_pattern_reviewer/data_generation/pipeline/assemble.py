"""Assemble receipts + expected rows from seeds (labels) and raw (text). Code computes all numbers. Decontaminates against eval INPUT text only.
Usage: python3 assemble.py <set_name>"""
import json, sys, re, random, unicodedata, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "pipeline"))
from make_seeds import CATS, ARCH
name = sys.argv[1]
FX = {"USD":1,"GBP":1.27,"EUR":1.08,"INR":0.012,"SGD":0.74,"AUD":0.65,"CAD":0.73,"MXN":0.055,"BRL":0.18,"JPY":0.0067}
ZERO_DEC = {"JPY","INR","MXN"}
MCCD = {"5812":"Eating places and restaurants","5813":"Drinking places (alcoholic beverages)","5411":"Grocery stores and supermarkets","5921":"Package stores (beer, wine, liquor)",
 "5912":"Drug stores and pharmacies","7011":"Lodging (hotels, motels, resorts)","4511":"Airlines and air carriers","4121":"Taxicabs and limousines","5732":"Electronics stores",
 "5943":"Stationery and office supply stores","5734":"Computer software stores","5947":"Gift, card, novelty and souvenir shops","5311":"Department stores","5651":"Family clothing stores",
 "5499":"Miscellaneous food stores and convenience stores","7992":"Public golf courses","7922":"Theatrical producers and ticket agencies","7995":"Betting and gambling","7216":"Dry cleaners",
 "4812":"Telecommunication equipment and telephone sales","5993":"Cigar stores and stands","5944":"Jewelry stores","7230":"Beauty and barber shops","7399":"Business services"}
def norm(s): return re.sub(r"[\W\d_]+", " ", unicodedata.normalize("NFKC", s).casefold()).strip()
def grams(s, n=3):
    s = " " + norm(s) + " "; return {s[i:i+n] for i in range(max(1, len(s)-n+1))}
def jac(a, b): return len(a & b) / max(1, len(a | b))

rng = random.Random(7)
seeds = {r["seed_id"]: r for r in json.loads((HERE/"seeds"/f"{name}_ALL.json").read_text())}
raw = {}
for p in sorted((HERE/"raw").glob(f"{name}_chunk*.json")):
    for r in json.loads(p.read_text()): raw[r["seed_id"]] = r
missing = [s for s in seeds if s not in raw]
# eval input text (inputs only; never labels)
EV = []
for p in ("/Users/geboou/Desktop/oversight/validator/data_heldout/receipts_input.jsonl", "/Users/geboou/Desktop/oversight/validator/data_split/receipts_input.jsonl"):
    for x in open(p):
        if x.strip(): EV += [l["description_raw"] for l in json.loads(x)["line_items"]]
EVN = {norm(d) for d in EV}; EVG = [(d, grams(d)) for d in EV]
rec_out, exp_out, flagged, errors = [], [], [], []
for sid, sd in seeds.items():
    if sid not in raw: continue
    rw = raw[sid]; byslot = {l["slot_id"]: l for l in rw["lines"]}
    lines, ok = [], True
    for i, slot in enumerate(sd["lines"], 1):
        t = byslot.get(slot["slot_id"])
        if not t: errors.append((sid, "missing slot " + slot["slot_id"])); ok = False; continue
        q, up = t.get("quantity"), t.get("unit_price")
        if not (isinstance(q, int) and q >= 1 and isinstance(up, (int, float)) and up > 0 and t.get("description_raw", "").strip() and t.get("description_en", "").strip()):
            errors.append((sid, "bad fields " + slot["slot_id"])); ok = False; continue
        cur = sd["currency"]; amt = round(q * up, 0 if cur in ZERO_DEC else 2); fx = FX[cur]
        lines.append({"line_id": f"{sid}-L{i}", "description_raw": t["description_raw"].strip(), "language": sd["language"], "quantity": q,
                      "unit_price": up, "amount": amt, "amount_usd": round(amt * fx, 2), "_slot": slot, "_t": t})
    if not ok: continue
    cur = sd["currency"]; total = round(sum(l["amount"] for l in lines), 0 if cur in ZERO_DEC else 2)
    meal = sd["submitted_expense_type"] in ("Meals - Individual", "Meals - Team", "Client Entertainment")
    rec = {"receipt_id": sid, "employee_id": f"E-{rng.randint(9100, 9999)}", "employee_country": sd["country"], "entity": sd["entity"],
           "submitted_expense_type": sd["submitted_expense_type"], "merchant_name": rw["merchant_name"], "mcc": sd["mcc"], "mcc_description": MCCD[sd["mcc"]],
           "transaction_datetime": f"2026-{rng.randint(1,10):02d}-{rng.randint(1,28):02d}T{rng.randint(8,22):02d}:{rng.choice(['00','15','30','45'])}:00",
           "currency": cur, "fx_rate_to_usd": FX[cur], "total_amount": total, "total_amount_usd": round(total * FX[cur], 2),
           "attendee_count": rng.randint(2, 6) if meal else None, "trip_id": None, "trip_nights": None, "pre_approval_ref": None, "itemized": True,
           "line_items": [{k: v for k, v in l.items() if not k.startswith("_")} for l in lines]}
    rec_out.append(rec)
    for l in lines:
        s, t = l["_slot"], l["_t"]
        alts = [a for a in t.get("acceptable_alternatives", []) if a in CATS and a != s["category"]]
        e = {"receipt_id": sid, "line_id": l["line_id"], "category": s["category"], "other_kind": s["other_kind"], "acceptable_alternatives": alts,
             "genuinely_ambiguous": s["target_confidence"] == "low" or bool(alts), "expected_confidence": s["target_confidence"],
             "gift_recipient": s["recipient"], "slice": s["slice"], "language": s["language"], "description_en": t["description_en"],
             "note": t.get("note") if s["category"] == "other" else None, "why": t.get("why", "")}
        exp_out.append(e)
        d = l["description_raw"]; reason = None
        if norm(d) in EVN: reason = "exact match with an existing eval line"
        else:
            g = grams(d)
            best = max(((jac(g, eg), ed) for ed, eg in EVG), default=(0, ""))
            if best[0] >= 0.6: reason = f"char-trigram Jaccard {best[0]:.2f} with existing line {best[1]!r}"
        if reason: flagged.append({"line_id": l["line_id"], "description_raw": d, "reason": reason})
bad = {f["line_id"] for f in flagged}
(HERE/f"{name}_receipts.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rec_out) + "\n")
(HERE/f"{name}_expected.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in exp_out) + "\n")
(HERE/f"{name}_flagged_decontam.json").write_text(json.dumps(flagged, ensure_ascii=False, indent=1))
print(f"{name}: receipts {len(rec_out)}/{len(seeds)} lines {len(exp_out)} missing-chunks {len(missing)} errors {len(errors)} flagged_vs_eval {len(flagged)}")
for e in errors[:8]: print("ERR", e)
print("category min", min(collections.Counter(e["category"] for e in exp_out).values()), "conf", dict(collections.Counter(e["expected_confidence"] for e in exp_out)))
