"""Pattern benchmark v1 for the cross-receipt reviewer. Run inside the validator env (needs validator.engine).
Histories = one employee's receipts over ~30 days. Planted patterns are known by construction. The ENGINE runs on every history (oracle categories)
so we know which receipts the engine passes: those are the only ones the reviewer may escalate."""
import json, random, copy, collections, sys
from pathlib import Path
from validator.engine import run_engine
from validator.normaliser import normalise_receipt
HERE = Path("/Users/geboou/Desktop/oversight/finetune/data_synth")
rng = random.Random(20261029)
POOL, CAT = [], {}
for n in ("train",):
    exp = {}
    for l in open(HERE / f"trainv1_clean_{n}_expected.jsonl"):
        d = json.loads(l); exp[d["line_id"]] = d
    for l in open(HERE / f"trainv1_clean_{n}_receipts.jsonl"):
        r = json.loads(l)
        if len(r["line_items"]) <= 4 and r["itemized"] and not any(exp[li["line_id"]]["slice"] == "injection" for li in r["line_items"]):
            POOL.append((r, {li["line_id"]: exp[li["line_id"]]["category"] for li in r["line_items"]}))
by_ent = collections.defaultdict(list)
n_pool0 = len(POOL)
for r, c in POOL:
    if r["entity"] not in ("GLOBAL", "APAC"): continue   # EMEA needs a EUR rate in the batch (REG-04): keep the experiment simple
    r2 = dict(r, submitted_expense_type={"Technology":"Computer Equipment","Other":"Office Supplies","Travel - Air":"Travel - Other","Travel - Ground":"Travel - Other","Travel - Lodging":"Lodging"}.get(r["submitted_expense_type"], r["submitted_expense_type"]))
    x = run_engine([normalise_receipt(r2)], c, None, None)[r2["receipt_id"]]
    if str(x.disposition) == "pass": by_ent[r2["entity"]].append((r2, c))
print("pool", n_pool0, "-> engine-pass filler receipts:", {k: len(v) for k, v in by_ent.items()})
NAMES = ["Linda Chen", "Marco Bellini", "Aiko Tanaka", "Sven Larsson", "Priya Raman", "Omar Haddad", "Julia Weber", "Tomás Ortega", "Hana Kim", "Peter Novak"]
FIRMS = ["Acme Ltd", "Norvik GmbH", "Kestrel SA", "Pinewood LLC", "Orion KK", "Delta SpA"]
GIFTS = ["Gift basket", "Wine-free tea set", "Branded leather folio", "Orchid arrangement", "Chocolate hamper", "Desk plant gift set"]
DOCKS = ["USB-C docking station 4-port", "Thunderbolt dock 8-in-1", "Monitor arm dual", "USB hub 10-port powered", "Wireless keyboard and mouse combo"]
def base(rid, emp, ent, country, day, hour, mcc, mccd, merchant, etype):
    return {"receipt_id": rid, "employee_id": emp, "employee_country": country, "entity": ent, "submitted_expense_type": etype, "merchant_name": merchant,
            "mcc": mcc, "mcc_description": mccd, "transaction_datetime": f"2026-05-{day:02d}T{hour:02d}:{rng.choice(['00','15','30','45'])}:00",
            "currency": "USD", "fx_rate_to_usd": 1, "attendee_count": None, "trip_id": None, "trip_nights": None, "pre_approval_ref": None, "itemized": True}
def one_line(r, desc, price, qty=1):
    amt = round(price * qty, 2)
    r["line_items"] = [{"line_id": r["receipt_id"] + "-L1", "description_raw": desc, "language": "en", "quantity": qty, "unit_price": price, "amount": amt, "amount_usd": amt}]
    r["total_amount"] = amt; r["total_amount_usd"] = amt
    return r
def gift_receipt(rid, emp, ent, country, day, name, firm, price):
    r = base(rid, emp, ent, country, day, rng.randint(10, 17), "5947", "Gift, card, novelty and souvenir shops", rng.choice(["Giftery & Co", "The Present Studio", "Bloom & Parcel"]), "Client Gifts")
    return one_line(r, f"{rng.choice(GIFTS)} for client {name} ({firm})", price), {r["receipt_id"] + "-L1": "gift"}, {r["receipt_id"] + "-L1": ("client", name)}
def tech_receipt(rid, emp, ent, country, day, desc, price, pa=None):
    r = base(rid, emp, ent, country, day, rng.randint(9, 18), "5045", "Computers, peripherals and software", rng.choice(["Circuit Hub", "PixelWorks Store", "Volt & Co"]), "Computer Equipment")
    r["pre_approval_ref"] = pa
    return one_line(r, desc, price), {r["receipt_id"] + "-L1": "computer_accessory"}, None
def coffee_receipt(rid, emp, ent, country, day):
    r = base(rid, emp, ent, country, day, rng.randint(7, 10), "5814", "Fast food restaurants", "Corner Coffee Roasters", "Meals - Individual")
    price = round(rng.uniform(5.5, 12.5), 2); r["attendee_count"] = 1
    return one_line(r, rng.choice(["Flat white", "Cappuccino + croissant", "Cold brew", "Latte"]), price), {r["receipt_id"] + "-L1": "food_beverage"}, None
def history(hid, kind):
    ent = rng.choice(list(by_ent)); emp = f"E-8{rng.randint(100, 999)}"
    sample = rng.sample(by_ent[ent], 7)
    recs, cats, gf, planted = [], {}, {}, []
    country = sample[0][0]["employee_country"]
    days = sorted(rng.sample(range(1, 29), 12))
    k = 0
    for r, c in sample:
        r = copy.deepcopy(r); k += 1; old = r["receipt_id"]
        r["receipt_id"] = f"{hid}-R{k:02d}"; r["employee_id"] = emp; r["employee_country"] = country
        r["transaction_datetime"] = f"2026-05-{days[k-1]:02d}" + r["transaction_datetime"][10:]
        for i, li in enumerate(r["line_items"], 1):
            nl = f"{r['receipt_id']}-L{i}"; cats[nl] = c[li["line_id"]]; li["line_id"] = nl
        recs.append(r)
    ent_i = f"{hid}"
    def add(t):
        r, c, g = t; recs.append(r); cats.update(c)
        if g: gf.update(g)
        return r["receipt_id"]
    nxt = len(recs)
    if kind == "gift_splitting":
        name, firm = rng.choice(NAMES), rng.choice(FIRMS); ds = sorted(rng.sample(range(1, 29), rng.choice([3, 4])))
        for d in ds:
            nxt += 1; planted.append(add(gift_receipt(f"{hid}-R{nxt:02d}", emp, ent, country, d, name, firm, round(rng.uniform(38, 49.9), 2))))
    elif kind == "duplicate_submission":
        src = copy.deepcopy(rng.choice(recs)); nxt += 1
        orig = src["receipt_id"]; src["receipt_id"] = f"{hid}-R{nxt:02d}"
        for i, li in enumerate(src["line_items"], 1):
            nl = f"{src['receipt_id']}-L{i}"; cats[nl] = cats[li["line_id"]]; li["line_id"] = nl
        recs.append(src); planted.append(src["receipt_id"])
    elif kind == "just_under_threshold":
        ds = sorted(rng.sample(range(1, 29), 4))
        for d in ds:
            nxt += 1; planted.append(add(tech_receipt(f"{hid}-R{nxt:02d}", emp, ent, country, d, rng.choice(DOCKS), round(rng.uniform(195, 199.9), 2))))
    elif kind == "clean":
        flavor = rng.choice(["coffee", "gifts_different", "tech_preapproved", "plain"])
        if flavor == "coffee":
            for d in sorted(rng.sample(range(1, 29), 5)):
                nxt += 1; add(coffee_receipt(f"{hid}-R{nxt:02d}", emp, ent, country, d))
        elif flavor == "gifts_different":
            for d, nm in zip(sorted(rng.sample(range(1, 29), 3)), rng.sample(NAMES, 3)):
                nxt += 1; add(gift_receipt(f"{hid}-R{nxt:02d}", emp, ent, country, d, nm, rng.choice(FIRMS), round(rng.uniform(25, 49), 2)))
        elif flavor == "tech_preapproved":
            for d in sorted(rng.sample(range(1, 29), 2)):
                nxt += 1; add(tech_receipt(f"{hid}-R{nxt:02d}", emp, ent, country, d, rng.choice(DOCKS), round(rng.uniform(260, 480), 2), pa=f"PA-2026-{rng.randint(1000, 9999)}"))
    recs.sort(key=lambda r: r["transaction_datetime"])
    res = run_engine([normalise_receipt(r) for r in recs], cats, gf or None, None)
    for r in recs:
        x = res[r["receipt_id"]]
        r["_engine"] = {"disposition": str(x.disposition), "fired": sorted({c.rule_id for c in x.checks if c.status == "fired"})}
    return {"history_id": hid, "kind": kind, "employee_id": emp, "entity": ent, "planted_receipts": planted, "receipts": recs,
            "_cats": cats}
H = []; i = 0
for kind, n in (("gift_splitting", 20), ("duplicate_submission", 20), ("just_under_threshold", 20), ("clean", 30)):
    for _ in range(n):
        i += 1; H.append(history(f"PH{i:03d}", kind))
json.dump(H, open(HERE / "patterns_v1.json", "w"), ensure_ascii=False)
# report: does the engine pass the planted receipts?
st = collections.Counter(); alld = collections.Counter()
for h in H:
    for r in h["receipts"]:
        alld[r["_engine"]["disposition"]] += 1
        if r["receipt_id"] in h["planted_receipts"]: st[(h["kind"], r["_engine"]["disposition"])] += 1
print("histories", len(H), "receipts", sum(len(h["receipts"]) for h in H))
print("all receipts by engine disposition", dict(alld))
print("planted receipts by (pattern, engine disposition):", dict(st))
