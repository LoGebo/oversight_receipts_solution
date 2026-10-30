"""Seeds for the synthetic generator. CODE decides every label (category, slice, target confidence, recipient, injection);
the LLM only writes surface text. Usage: python3 make_seeds.py <set_name> <n_lines> <rng_seed> <chunk_receipts>"""
import json, random, sys, collections
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "seeds"
CATS = ["alcohol","tobacco","personal_electronics","gift","gift_card","household_goods","personal_care","clothing","gambling","jewelry",
        "food_beverage","computer_accessory","office_supplies","lodging","ground_transport","airfare","laundry_service","health_otc",
        "software_subscription","service_fee","other"]
EXT = ["mobile_handset", "entertainment_venue", "prescription_medication"]
SLICES = {  # name: (share, eligible categories, confidence mix high/medium/low)
 "plain":        (12, CATS, (95, 5, 0)),
 "trap_names_lie": (18, ["alcohol","food_beverage","household_goods","health_otc","personal_care","tobacco","gift"], (25, 50, 25)),
 "brand_no_hint":  (10, ["alcohol","tobacco","personal_electronics","software_subscription","computer_accessory","clothing","food_beverage","health_otc"], (45, 40, 15)),
 "gift_vs_goods":  (8, ["gift","office_supplies","jewelry","household_goods","clothing","food_beverage"], (30, 50, 20)),
 "recipient_in_text": (10, ["gift","gift_card","jewelry","alcohol","personal_care","food_beverage"], (75, 20, 5)),
 "dirty_text":   (12, CATS, (40, 40, 20)),
 "injection":    (6, [c for c in CATS if c != "other"], (80, 15, 5)),
 "service_vs_tip": (8, ["service_fee","food_beverage","ground_transport","lodging"], (70, 25, 5)),
 "extension_items": (8, ["other"], (50, 35, 15)),
 "restricted_boundary": (8, ["personal_care","health_otc","gift","office_supplies","household_goods","personal_electronics","computer_accessory"], (25, 50, 25)),
}
LANG = {"en": 25, "es": 15, "fr": 15, "de": 15, "pt": 12, "ja": 18}
COUNTRY = {"en": [("US","USD","GLOBAL"),("GB","GBP","EMEA"),("IN","INR","APAC"),("SG","SGD","APAC"),("AU","AUD","APAC"),("CA","CAD","GLOBAL")],
           "es": [("ES","EUR","EMEA"),("MX","MXN","GLOBAL")], "fr": [("FR","EUR","EMEA"),("CA","CAD","GLOBAL")],
           "de": [("DE","EUR","EMEA"),("AT","EUR","EMEA")], "pt": [("BR","BRL","GLOBAL"),("PT","EUR","EMEA")], "ja": [("JP","JPY","APAC")]}
# natural merchant archetype per category (used 75% of the time; otherwise a misleading one)
ARCH = {"restaurant":"5812","bar":"5813","grocery":"5411","liquor_store":"5921","pharmacy":"5912","hotel":"7011","airline":"4511","taxi_rideshare":"4121",
        "electronics_store":"5732","stationery_store":"5943","software_online":"5734","gift_shop":"5947","department_store":"5311","clothing_store":"5651",
        "convenience_store":"5499","golf_club":"7992","theatre_venue":"7922","casino":"7995","dry_cleaner":"7216","phone_store":"4812","tobacco_shop":"5993",
        "jewelry_store":"5944","salon_spa":"7230","business_services":"7399"}
NATURAL = {"alcohol":["bar","liquor_store","restaurant"],"tobacco":["tobacco_shop","convenience_store"],"personal_electronics":["electronics_store"],
 "gift":["gift_shop","department_store"],"gift_card":["department_store","gift_shop"],"household_goods":["department_store","grocery"],
 "personal_care":["salon_spa","pharmacy","department_store"],"clothing":["clothing_store","department_store"],"gambling":["casino"],"jewelry":["jewelry_store"],
 "food_beverage":["restaurant","grocery","convenience_store"],"computer_accessory":["electronics_store"],"office_supplies":["stationery_store"],
 "lodging":["hotel"],"ground_transport":["taxi_rideshare"],"airfare":["airline"],"laundry_service":["dry_cleaner","hotel"],"health_otc":["pharmacy"],
 "software_subscription":["software_online"],"service_fee":["restaurant","hotel","business_services"],"other":["phone_store","golf_club","theatre_venue","pharmacy"]}
STYLES = ["terse POS abbreviation","full product name","e-commerce listing title","restaurant menu item","handwritten-looking","delivery-app item","hotel folio line","ticket-style line"]
PERSONAS = ["small family shop owner","hotel front desk clerk","airport kiosk cashier","corporate caterer","street-market vendor","chain-store cashier","boutique owner","online marketplace seller"]
EXPENSE = {"restaurant":["Meals - Individual","Meals - Team","Client Entertainment"],"bar":["Client Entertainment","Meals - Team"],"hotel":["Travel - Lodging","Meals - Individual"],
 "airline":["Travel - Air"],"taxi_rideshare":["Travel - Ground"],"software_online":["Technology","Other"],"electronics_store":["Technology","Other"],
 "stationery_store":["Office Supplies"],"gift_shop":["Client Gifts","Other"],"department_store":["Client Gifts","Other","Office Supplies"]}

def pick_w(rng, d):
    ks = list(d); return rng.choices(ks, weights=[d[k] for k in ks])[0]

def main(name, n_lines, seed, chunk):
    rng = random.Random(seed)
    used = collections.Counter(); slots = []
    for i in range(n_lines):
        sl = pick_w(rng, {k: v[0] for k, v in SLICES.items()})
        elig = SLICES[sl][1]; m = min(used[c] for c in elig)
        cat = rng.choice([c for c in elig if used[c] == m]); used[cat] += 1
        conf = rng.choices(["high","medium","low"], weights=SLICES[sl][2])[0]
        lang = pick_w(rng, LANG)
        slot = {"slot_id": f"{name}-S{i+1:04d}", "category": cat, "slice": sl, "target_confidence": conf, "language": lang,
                "style": rng.choice(STYLES), "persona": rng.choice(PERSONAS), "other_kind": "none", "recipient": None, "injection": sl == "injection"}
        if cat == "other":
            slot["other_kind"] = rng.choice(EXT + ["none"]) if sl != "extension_items" else rng.choice(EXT)
        if sl == "recipient_in_text":
            slot["recipient"] = {"kind": rng.choice(["client","employee","government_official","government_official","client"]), "named": rng.random() < 0.6}
        slots.append(slot)
    # group into receipts (2-5 lines), same language per receipt, by natural archetype
    slots.sort(key=lambda s: (s["language"], NATURAL[s["category"]][0]))
    receipts, i = [], 0
    while i < len(slots):
        k = rng.choice([2, 3, 3, 4, 5]); grp = []
        lang = slots[i]["language"]
        while i < len(slots) and len(grp) < k and slots[i]["language"] == lang:
            grp.append(slots[i]); i += 1
        c0 = grp[0]["category"]
        arch = rng.choice(NATURAL[c0]) if rng.random() < 0.75 else rng.choice(list(ARCH))
        country, cur, ent = rng.choice(COUNTRY[lang])
        et = rng.choice(EXPENSE.get(arch, ["Other", "Client Gifts", "Office Supplies", "Meals - Team"]))
        receipts.append({"seed_id": f"{name}-R{len(receipts)+1:03d}", "language": lang, "archetype": arch, "mcc": ARCH[arch], "country": country,
                         "currency": cur, "entity": ent, "submitted_expense_type": et, "lines": grp})
    OUT.mkdir(exist_ok=True)
    chunks = [receipts[j:j + chunk] for j in range(0, len(receipts), chunk)]
    for n, ch in enumerate(chunks, 1):
        (OUT / f"{name}_chunk{n:02d}.json").write_text(json.dumps(ch, ensure_ascii=False, indent=1))
    (OUT / f"{name}_ALL.json").write_text(json.dumps(receipts, ensure_ascii=False))
    cc = collections.Counter(s["category"] for r in receipts for s in r["lines"])
    print(name, "receipts", len(receipts), "lines", sum(len(r["lines"]) for r in receipts), "chunks", len(chunks))
    print("min per category", min(cc.values()), dict(collections.Counter(s["slice"] for r in receipts for s in r["lines"])))
    print("conf", dict(collections.Counter(s["target_confidence"] for r in receipts for s in r["lines"])), "lang", dict(collections.Counter(r["language"] for r in receipts)))

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
