"""Pattern dataset v2 (fraud the deterministic engine PASSES). Run in the validator env.
8 families grounded in real engine thresholds; code builds every history; the ENGINE verifies that all receipts pass; vocabulary comes from LLM pools."""
import json, random, copy, collections, sys
from pathlib import Path
from validator.engine import run_engine
from validator.normaliser import normalise_receipt
HERE = Path("/Users/geboou/Desktop/oversight/finetune/data_synth")
P = {}
for f in ("pool_A", "pool_B", "pool_C"):
    for k, v in json.load(open(HERE / "pools" / f"{f}.json")).items(): P[k] = v
BYLANG = {k: collections.defaultdict(list) for k in P}
for k, v in P.items():
    for e in v: BYLANG[k][e["lang"]].append(e["text"])
LANGS = ["en", "es", "fr", "de", "pt", "ja"]
LOC = {"en": [("US", "GLOBAL"), ("IN", "APAC"), ("SG", "APAC"), ("AU", "APAC"), ("CA", "GLOBAL")], "es": [("MX", "GLOBAL")], "fr": [("CA", "GLOBAL")],
       "de": [("CH", "GLOBAL")], "pt": [("BR", "GLOBAL")], "ja": [("JP", "APAC")]}
MCC = {"gift": ("5947", "Gift, card, novelty and souvenir shops"), "tech": ("5045", "Computers, peripherals and software"), "rest": ("5812", "Eating places and restaurants"),
       "cafe": ("5814", "Fast food restaurants"), "gen": ("7399", "Business services"), "office": ("5943", "Stationery and office supply stores"),
       "taxi": ("4121", "Taxicabs and limousines"), "hotel": ("7011", "Lodging (hotels, motels, resorts)")}
REJ_WHY = collections.defaultdict(collections.Counter)
class G:
    def __init__(s, seed, lang):
        s.r = random.Random(seed); s.lang = lang; s.k = 0
        s.country, s.ent = s.r.choice(LOC[lang]); s.emp = f"E-8{s.r.randint(100, 999)}"; s.trip = f"TRIP-{s.r.randint(1000, 9999)}"
    def pick(s, topic, lang=None):
        l = lang or s.lang; return s.r.choice(BYLANG[topic][l] or BYLANG[topic]["en"])
    def rid(s, hid): s.k += 1; return f"{hid}-R{s.k:02d}"
    def base(s, hid, day, kind, merchant, etype, hour=None):
        mcc, mccd = MCC[kind]
        return {"receipt_id": s.rid(hid), "employee_id": s.emp, "employee_country": s.country, "entity": s.ent, "submitted_expense_type": etype, "merchant_name": merchant,
                "mcc": mcc, "mcc_description": mccd, "transaction_datetime": f"2026-05-{day:02d}T{hour or s.r.randint(8, 20):02d}:{s.r.choice(['00','15','30','45'])}:00",
                "currency": "USD", "fx_rate_to_usd": 1, "attendee_count": None, "trip_id": None, "trip_nights": None, "pre_approval_ref": None, "itemized": True}
    def line(s, r, desc, price, qty=1, cat="other"):
        amt = round(price * qty, 2); lid = r["receipt_id"] + "-L1"
        r["line_items"] = [{"line_id": lid, "description_raw": desc, "language": s.lang, "quantity": qty, "unit_price": price, "amount": amt, "amount_usd": amt}]
        r["total_amount"] = amt; r["total_amount_usd"] = amt
        return r, {lid: cat}
    # ---- receipt builders: return (receipt, {line: category}, gift_for or None)
    def gift(s, hid, day, name=None, firm=None, price=None):
        name = name or s.pick("person_names"); firm = firm or s.pick("firms"); price = price or round(s.r.uniform(32, 49.9), 2)
        r = s.base(hid, day, "gift", s.pick("gift_merchants"), "Client Gifts")
        d = s.pick("gift_templates").replace("{item}", s.pick("gift_items")).replace("{name}", name).replace("{firm}", firm)
        r, c = s.line(r, d, price, cat="gift"); return r, c, {r["receipt_id"] + "-L1": ("client", name)}
    def small_gift(s, hid, day):
        r = s.base(hid, day, "gift", s.pick("gift_merchants"), "Client Gifts")
        r, c = s.line(r, s.pick("unnamed_gift_items"), round(s.r.uniform(6.5, 9.9), 2), cat="gift"); return r, c, None
    def tech(s, hid, day, price, pa=None):
        r = s.base(hid, day, "tech", s.pick("electronics_merchants"), "Computer Equipment"); r["pre_approval_ref"] = pa
        r, c = s.line(r, s.pick("tech_items"), price, cat="computer_accessory"); return r, c, None
    def nonitem(s, hid, day, price):
        r = s.base(hid, day, "gen", s.pick("generic_merchants"), "Office Supplies"); r["itemized"] = False
        r, c = s.line(r, s.pick("total_lines"), price, cat="other"); return r, c, None
    def meal(s, hid, day, price):
        r = s.base(hid, day, "rest", s.pick("restaurant_merchants"), "Meals - Individual", hour=s.r.choice([12, 13, 19, 20])); r["attendee_count"] = 1; r["trip_id"] = s.trip; r["trip_nights"] = 4
        r, c = s.line(r, s.pick("meal_items"), price, cat="food_beverage"); return r, c, None
    def team_meal(s, hid, day, price, n, merchant):
        r = s.base(hid, day, "rest", merchant, "Meals - Team", hour=s.r.choice([12, 13, 19])); r["attendee_count"] = n
        r, c = s.line(r, s.pick("meal_items"), round(price / n, 2), qty=n, cat="food_beverage"); return r, c, None
    def coffee(s, hid, day):
        r = s.base(hid, day, "cafe", s.pick("restaurant_merchants"), "Meals - Individual", hour=s.r.randint(7, 10)); r["attendee_count"] = 1; r["trip_id"] = s.trip; r["trip_nights"] = 4
        r, c = s.line(r, s.pick("coffee_items"), round(s.r.uniform(4.5, 12), 2), cat="food_beverage"); return r, c, None
    def office(s, hid, day, price=None):
        r = s.base(hid, day, "office", s.pick("generic_merchants"), "Office Supplies")
        r, c = s.line(r, s.pick("office_items"), price or round(s.r.uniform(8, 70), 2), cat="office_supplies"); return r, c, None
    def taxi(s, hid, day):
        r = s.base(hid, day, "taxi", s.pick("generic_merchants"), "Travel - Other"); r["trip_id"] = s.trip; r["trip_nights"] = 4
        r, c = s.line(r, s.pick("taxi_items"), round(s.r.uniform(12, 55), 2), cat="ground_transport"); return r, c, None
    def filler(s, hid, day):
        return s.r.choice([lambda: s.office(hid, day), lambda: s.taxi(hid, day), lambda: s.coffee(hid, day), lambda: s.meal(hid, day, round(s.r.uniform(14, 48), 2)),
                           lambda: s.tech(hid, day, round(s.r.uniform(35, 150), 2))])()
FAMILIES = ["gift_splitting", "gift_under_naming", "tech_just_under", "itemize_just_under", "meal_cap_hugging", "meal_just_under_doc", "duplicate_submission", "pa_reuse"]
SEEN = FAMILIES[:5]; UNSEEN = FAMILIES[5:]
REASON = {"gift_splitting": "Several gifts to the same named client on different days, each just under the $50 per-receipt cap (the cap applies per receipt).",
          "gift_under_naming": "Many unnamed gifts each just under $10, the amount from which a recipient must be named.",
          "tech_just_under": "Repeated equipment purchases priced just under $200, the per-item level that requires pre-approval.",
          "itemize_just_under": "Repeated non-itemized receipts just under $75, the amount above which itemization is required.",
          "meal_cap_hugging": "Individual meals repeatedly at 96-99% of the per-person daily meal cap.",
          "meal_just_under_doc": "Team meals repeatedly just under $150, the receipt total above which attendee documentation is needed.",
          "duplicate_submission": "The same expense submitted twice with different receipt ids.",
          "pa_reuse": "One pre-approval reference reused to cover several separate large purchases."}
def make(hid, family, seed):
    lang = random.Random(seed).choice(LANGS); g = G(seed, lang); r = g.r
    recs, cats, gf, planted = [], {}, {}, []
    flavors = []
    days = sorted(r.sample(range(1, 29), 16)); used = 0
    def nd():
        nonlocal used; used += 1; return days[used - 1]
    def add(t, plant=False):
        rec, c, gg = t; recs.append(rec); cats.update(c)
        if gg: gf.update(gg)
        if plant: planted.append(rec["receipt_id"])
        return rec
    for _ in range(r.randint(4, 7)): add(g.filler(hid, nd()))
    cap = 59 if g.ent == "APAC" else 74
    if family == "gift_splitting":
        name, firm = g.pick("person_names"), g.pick("firms")
        for _ in range(r.choice([3, 4, 5])): add(g.gift(hid, nd(), name, firm), True)
    elif family == "gift_under_naming":
        for _ in range(r.randint(5, 8)): add(g.small_gift(hid, nd()), True)
    elif family == "tech_just_under":
        for _ in range(r.randint(3, 5)): add(g.tech(hid, nd(), round(r.uniform(194, 199.9), 2)), True)
    elif family == "itemize_just_under":
        for _ in range(r.randint(3, 5)): add(g.nonitem(hid, nd(), round(r.uniform(72.5, 74.95), 2)), True)
    elif family == "meal_cap_hugging":
        for _ in range(r.randint(4, 6)): add(g.meal(hid, nd(), round(r.uniform(cap - 2.2, cap + .9), 2)), True)
    elif family == "meal_just_under_doc":
        m = g.pick("restaurant_merchants")
        for _ in range(r.randint(3, 5)): add(g.team_meal(hid, nd(), round(r.uniform(144, 149.9), 2), r.choice([4, 5, 6]), m), True)
    elif family == "duplicate_submission":
        src = copy.deepcopy(r.choice(recs)); src["receipt_id"] = g.rid(hid)
        for i, li in enumerate(src["line_items"], 1):
            nl = f"{src['receipt_id']}-L{i}"; cats[nl] = cats[li["line_id"]]; li["line_id"] = nl
        if r.random() < .4: src["transaction_datetime"] = src["transaction_datetime"][:8] + f"{min(28, int(src['transaction_datetime'][8:10]) + 1):02d}" + src["transaction_datetime"][10:]
        recs.append(src); planted.append(src["receipt_id"])
    elif family == "pa_reuse":
        pa = f"PA-2026-{r.randint(1000, 9999)}"
        for _ in range(r.choice([3, 4])): add(g.tech(hid, nd(), round(r.uniform(260, 520), 2), pa=pa), True)
    elif family == "clean":
        for fl in r.sample(["gifts_different", "one_named_gift_and_tokens", "tech_varied", "tech_preapproved_once_each", "nonitem_small", "meals_varied",
                            "team_meals_varied", "coffee_regular", "plain"], 2):
            flavors.append(fl)
            if fl == "gifts_different":
                for nm in r.sample(BYLANG["person_names"][lang] or BYLANG["person_names"]["en"], 3): add(g.gift(hid, nd(), nm, g.pick("firms")))
            elif fl == "one_named_gift_and_tokens":
                add(g.gift(hid, nd())); add(g.small_gift(hid, nd()))
            elif fl == "tech_varied":
                for _ in range(3): add(g.tech(hid, nd(), round(r.uniform(40, 185), 2)))
            elif fl == "tech_preapproved_once_each":
                for _ in range(2): add(g.tech(hid, nd(), round(r.uniform(260, 520), 2), pa=f"PA-2026-{r.randint(1000, 9999)}"))
            elif fl == "nonitem_small":
                for _ in range(3): add(g.nonitem(hid, nd(), round(r.uniform(8, 58), 2)))
            elif fl == "meals_varied":
                for _ in range(4): add(g.meal(hid, nd(), round(r.uniform(14, 52), 2)))
            elif fl == "team_meals_varied":
                m = g.pick("restaurant_merchants")
                for _ in range(3): add(g.team_meal(hid, nd(), round(r.uniform(70, 125), 2), r.choice([3, 4, 5]), m))
            elif fl == "coffee_regular":
                for _ in range(5): add(g.coffee(hid, nd()))
    recs.sort(key=lambda x: x["transaction_datetime"])
    res = run_engine([normalise_receipt(x) for x in recs], cats, gf or None, None)
    ok = True; why = []
    for x in recs:
        v = res[x["receipt_id"]]; x["_engine"] = {"disposition": str(v.disposition), "fired": sorted({c.rule_id for c in v.checks if c.status == "fired"})}
        if str(v.disposition) != "pass": ok = False; why += x["_engine"]["fired"]
    if not ok: REJ_WHY[family].update(why); return None
    return {"history_id": hid, "family": family, "flavors": flavors, "employee_id": g.emp, "entity": g.ent, "language": lang, "planted_receipts": planted,
            "reason": REASON.get(family, ""), "receipts": recs}
PLAN = [("train", SEEN, 300, 500), ("test_seen", SEEN, 40, 100), ("test_unseen", UNSEEN, 60, 180)]
if len(sys.argv) > 1 and sys.argv[1] == "small": PLAN = [("train", SEEN, 6, 10), ("test_unseen", UNSEEN, 4, 6)]
out = {"train": [], "test_seen": [], "test_unseen": []}; rej = collections.Counter(); seed = 10_000
for split, fams, n_per, n_clean in PLAN:
    for fam, n in [(f, n_per) for f in fams] + [("clean", n_clean)]:
        got = 0; tries = 0
        while got < n and tries < n * 25:
            seed += 1; tries += 1; hid = f"{split[:2].upper()}{seed}"
            h = make(hid, fam, seed)
            if h is None: rej[fam] += 1; continue
            h["split"] = split; out[split].append(h); got += 1
for split, hs in out.items():
    with open(HERE / f"patterns_v2_{split}.jsonl", "w") as f:
        for h in hs: f.write(json.dumps(h, ensure_ascii=False) + "\n")
print("why rejected:", {k: dict(v.most_common(4)) for k, v in REJ_WHY.items()})
print({s: len(h) for s, h in out.items()}, "receipts", sum(len(x["receipts"]) for h in out.values() for x in h), "rejected (engine not pass):", dict(rej))
