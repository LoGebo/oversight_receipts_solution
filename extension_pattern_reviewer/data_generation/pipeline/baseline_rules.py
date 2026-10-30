"""Deterministic cross-receipt baseline. A1 = rules for the 5 SEEN families only (FROZEN before scoring unseen/red-team). A2 = + the 3 unseen families (upper bound for 'rules written by someone who knows them').
Usage: python3 baseline_rules.py   (no engine needed; works on the saved histories)"""
import json, collections, re
D = "/Users/geboou/Desktop/oversight/finetune/data_synth/"
NAMES = {e["text"] for e in json.load(open(D + "pools/pool_A.json"))["person_names"]}
def name_in(desc):
    for n in NAMES:
        if n in desc: return n
    return None
def unit(r): return r["line_items"][0]["unit_price"]
def rules_A1(h):
    R = h["receipts"]; flagged = {}
    def flag(rid, why): flagged.setdefault(rid, why)
    # 1 gift splitting
    by = collections.defaultdict(list)
    for r in R:
        if r["submitted_expense_type"] == "Client Gifts":
            n = name_in(r["line_items"][0]["description_raw"])
            if n: by[n].append(r)
    for n, rs in by.items():
        if len(rs) >= 2 and sum(x["total_amount_usd"] for x in rs) > 50:
            for x in rs: flag(x["receipt_id"], "gift_splitting")
    # 2 unnamed small gifts
    sm = [r for r in R if r["submitted_expense_type"] == "Client Gifts" and not name_in(r["line_items"][0]["description_raw"]) and r["total_amount_usd"] < 10]
    if len(sm) >= 4:
        for x in sm: flag(x["receipt_id"], "gift_under_naming")
    # 3 tech just under
    t = [r for r in R if r["submitted_expense_type"] == "Computer Equipment" and 190 <= unit(r) <= 200]
    if len(t) >= 3:
        for x in t: flag(x["receipt_id"], "tech_just_under")
    # 4 itemize just under
    n4 = [r for r in R if r["itemized"] is False and 70 <= r["total_amount_usd"] <= 75]
    if len(n4) >= 3:
        for x in n4: flag(x["receipt_id"], "itemize_just_under")
    # 5 meal-cap hugging
    cap = 60 if (h.get("entity") or h["receipts"][0]["entity"]) == "APAC" else 75
    m = [r for r in R if r["submitted_expense_type"] == "Meals - Individual" and (r["total_amount_usd"] / max(1, r["attendee_count"] or 1)) >= .95 * cap]
    if len(m) >= 3:
        for x in m: flag(x["receipt_id"], "meal_cap_hugging")
    return flagged
def rules_A2(h):
    flagged = rules_A1(h); R = h["receipts"]
    t = [r for r in R if r["submitted_expense_type"] == "Meals - Team" and 140 <= r["total_amount_usd"] <= 150]
    byM = collections.defaultdict(list)
    for r in t: byM[r["merchant_name"]].append(r)
    for rs in byM.values():
        if len(rs) >= 3:
            for x in rs: flagged.setdefault(x["receipt_id"], "meal_just_under_doc")
    seen = {}
    for r in sorted(R, key=lambda x: x["transaction_datetime"]):
        k = (r["merchant_name"], r["transaction_datetime"][:10], r["total_amount_usd"], r["line_items"][0]["description_raw"])
        if k in seen: flagged.setdefault(r["receipt_id"], "duplicate")
        seen[k] = r
    pa = collections.defaultdict(list)
    for r in R:
        if r["pre_approval_ref"] and r["total_amount_usd"] > 200: pa[r["pre_approval_ref"]].append(r)
    for rs in pa.values():
        if len(rs) >= 3:
            for x in rs: flagged.setdefault(x["receipt_id"], "pa_reuse")
    return flagged
def evaluate(name, H, rule):
    fam = collections.defaultdict(lambda: [0, 0, 0, 0])  # planted receipts, caught, histories, histories caught
    clean_h = clean_alarm = fp_receipts = 0
    for h in H:
        fl = rule(h); pl = set(h["planted_receipts"]); f = h["family"]
        if f == "clean":
            clean_h += 1; clean_alarm += bool(fl); fp_receipts += len(fl)
        else:
            fam[f][0] += len(pl); fam[f][1] += len(pl & set(fl)); fam[f][2] += 1; fam[f][3] += bool(pl & set(fl))
    return fam, clean_h, clean_alarm, fp_receipts
if __name__ == "__main__":
    for sp in ("test_seen", "test_unseen", "redteam"):
        H = [json.loads(x) for x in open(D + f"patterns_v2_{sp}.jsonl")]
        for nm, rule in (("A1 (5 seen families)", rules_A1), ("A2 (all 8 known families)", rules_A2)):
            fam, ch, ca, fp = evaluate(sp, H, rule)
            tp = sum(v[0] for v in fam.values()); tc = sum(v[1] for v in fam.values()); hh = sum(v[2] for v in fam.values()); hc = sum(v[3] for v in fam.values())
            print(f"[{sp}] {nm}: planted receipts caught {tc}/{tp} ({100*tc/max(1,tp):.0f}%), histories detected {hc}/{hh}; clean histories with a false alarm {ca}/{ch}")
        if sp == "redteam":
            fam, *_ = evaluate(sp, H, rules_A2)
            print("   red-team schemes caught by A2:", {k: f"{v[3]}/{v[2]}" for k, v in sorted(fam.items()) if v[3]})
