"""Check red-team histories against the real engine. Usage (from the validator dir):
  PYTHONDONTWRITEBYTECODE=1 env -u ANTHROPIC_API_KEY -u OPENROUTER_API_KEY uv run --frozen --no-sync python ../finetune/data_synth/pipeline/check_redteam.py <in.json> [<out.json>]
Input: JSON list of histories {scheme, reason, language, receipts:[receipt + per-line `category` + optional `gift_for` {line_id:[kind,name]} + `planted` bool]}.
Prints, per history, whether EVERY receipt gets engine disposition `pass` (and which rules fired otherwise). Writes only passing histories to <out.json>."""
import json, sys, collections
from validator.engine import run_engine
from validator.normaliser import normalise_receipt
CATS = {"alcohol","tobacco","personal_electronics","gift","gift_card","household_goods","personal_care","clothing","gambling","jewelry","food_beverage","computer_accessory","office_supplies","lodging","ground_transport","airfare","laundry_service","health_otc","software_subscription","service_fee","other"}
H = json.load(open(sys.argv[1])); good = []; fails = collections.Counter()
for n, h in enumerate(H):
    try:
        recs, cats, gf = [], {}, {}
        seen_ids = set()
        for r in h["receipts"]:
            r = dict(r); planted = r.pop("planted", False)
            g = r.pop("gift_for", None) or {}
            for li in r["line_items"]:
                c = li.pop("category")
                assert c in CATS, f"bad category {c}"
                cats[li["line_id"]] = c
            for k, v in g.items(): gf[k] = (v[0], v[1])
            assert r["receipt_id"] not in seen_ids; seen_ids.add(r["receipt_id"])
            r["_planted"] = planted; recs.append(r)
        res = run_engine([normalise_receipt({k: v for k, v in r.items() if k != "_planted"}) for r in recs], cats, gf or None, None)
        bad = {}
        for r in recs:
            x = res[r["receipt_id"]]; r["_engine"] = {"disposition": str(x.disposition), "fired": sorted({c.rule_id for c in x.checks if c.status == "fired"})}
            if str(x.disposition) != "pass": bad[r["receipt_id"]] = r["_engine"]["fired"]
        if bad: print(f"#{n} {h.get('scheme')}: NOT PASS ->", bad); fails["engine"] += 1; continue
        h["planted_receipts"] = [r["receipt_id"] for r in recs if r["_planted"]]
        for r in recs: r.pop("_planted")
        if not h["planted_receipts"]: print(f"#{n}: no planted receipts"); fails["noplant"] += 1; continue
        good.append(h); print(f"#{n} {h.get('scheme')}: OK ({len(recs)} receipts, {len(h['planted_receipts'])} planted)")
    except Exception as e:
        print(f"#{n}: ERROR {type(e).__name__}: {str(e)[:160]}"); fails["error"] += 1
print("passing", len(good), "of", len(H), dict(fails))
if len(sys.argv) > 2: json.dump(good, open(sys.argv[2], "w"), ensure_ascii=False)
