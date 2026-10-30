"""Multi-family generator for the pattern-reviewer data (v2). Usage:
  python3 gen.py --model nano-gpt/deepseek/deepseek-v4.1-flash --family deepseek --cls fraud --n 4 --seed 100 --out out
Each history: skeleton by code -> prompt -> author model writes receipts as JSON -> validated against the skeleton AND the real engine
(all receipts must get `pass`) -> saved. Failed attempts get one or two retries with the exact error list."""
import argparse, json, random, re, subprocess, sys, os, copy, tempfile, glob, concurrent.futures as cf, datetime
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "entregable"))
import skeleton as SK
import engine_api as ea

DOMAINS = ["client gifts", "computer equipment and accessories", "meals (individual and team)", "lodging", "ground transport and rentals", "office supplies and consumables", "client entertainment", "approvals and pre-approval references"]
MECHS = ["splitting one amount across several receipts", "timing (dates, weekends, windows around a rule)", "repetition of an item or amount", "relabeling (the declared type or merchant does not fit the lines)", "quantity or headcount that does not fit the items", "identity of the recipient or attendee", "spatial or temporal impossibility between receipts", "reuse of a reference or approval", "near-duplicates with a small change"]
USED = "gift_splitting, many_unnamed_gifts, tech_just_under_200, itemize_just_under_75, meal_cap_hugging, team_meal_just_under_150, duplicate_submission, pa_reuse, weekend_client_entertainment, overlapping_lodging, recurring_item_merchant_rotation, trip_id_stretched, solo_meals_as_team, personal_goods_as_office, gift_baskets_as_team_meals, weekend_rides_under_trip_id, sequential_invoice_amounts, cloned_fare_rotating_cabs, round_dollar_restaurants, food_hall_split, gifts_to_client_family, rotating_gift_recipients, headcount_vs_items, family_outing_as_entertainment, trip_id_hopping, lodging_nights_exceed_trip, day_trip_with_lodging, two_places_one_day, attendee_padding, teleporting_employee, trip_id_recycled_for_commuting, weekend_stay_beyond_trip, price_creep, identical_booking_fee, office_exact_multiples, streaming_rig_from_accessories, competing_saas_tools, tip_double_dip, home_city_hotel_staycation, rental_car_with_parallel_rides, companion_travel_extras, serial_gift_occasions, standing_two_person_dinner, breakfast_on_bb_rate, many_printer_cartridges, storage_media_stockpile, overnight_cutoff_timestamps, tech_from_nontech_retailers, pa_number_mirrors_date, membership_sliced_weekly, household_linens_as_laundry, companion_fares_solo_trips, meals_only_phantom_trip, month_end_topup_round_total"

# External typology of expense-reimbursement fraud (standard occupational-fraud categories: mischaracterized, overstated, fictitious, multiple reimbursement).
# Used for the blind exam E6 so the schemes do not come from this project's own ideas.
TAXONOMY = [
 ("mischaracterized expenses", "personal purchases claimed as business purchases: personal dining, groceries, household or family items booked as meals, supplies or equipment"),
 ("mischaracterized expenses", "personal travel or leisure (a vacation, a weekend trip, a family outing) booked as a business trip or client entertainment"),
 ("mischaracterized expenses", "a business-looking merchant or description that hides what was really bought (the lines contradict the merchant or declared type)"),
 ("overstated expenses", "real purchases with inflated amounts: tips or service charges padded, quantities or headcounts inflated, a cheaper item claimed as a pricier one"),
 ("overstated expenses", "claiming more than was spent through rounding up, repeated small padding, or splitting the claim so each piece stays under a threshold"),
 ("overstated expenses", "per-diem-style claiming: meals or lodging claimed at the limit every day even when the circumstances do not support it"),
 ("fictitious expenses", "expenses for services or purchases that never happened, with plausible but invented merchants and sequential or too-regular amounts"),
 ("fictitious expenses", "receipts for trips, attendees or recipients that do not exist or cannot be where the report says (timing or location impossibility)"),
 ("fictitious expenses", "recurring small invented charges (subscriptions, memberships, parking) that appear every period at the same amount"),
 ("multiple reimbursement", "the same expense submitted twice with a small change (date, merchant spelling, amount rounding, split into lines)"),
 ("multiple reimbursement", "one purchase claimed under two different expense types or two different trips or attendees"),
 ("multiple reimbursement", "an expense also covered by something already paid (a hotel breakfast included in the rate, a car rental plus rides on the same days)"),
 ("approval abuse", "using or reusing an approval or exception reference to cover purchases it was not meant for, or inventing a reference that mirrors something else"),
 ("collusion-style patterns", "gifts or entertainment concentrated on one person, or on relatives of a person, above what a single occasion would justify"),
 ("timing manipulation", "claims bunched at the end of a period, placed just before or after a cut-off, or dated on days that make no business sense"),
 ("asset-style purchases", "equipment or consumables bought in quantities or varieties that no single employee would use (stockpiling or resale)"),
]
CATS = "gift, gift_card, household_goods, personal_care, clothing, food_beverage, computer_accessory, office_supplies, lodging, ground_transport, airfare, laundry_service, health_otc, software_subscription, service_fee, other"
FACTS = """ENGINE FACTS (every receipt must PASS the deterministic engine on its own):
- Currency USD only (fx 1). Allowed expense types: "Client Entertainment", "Client Gifts", "Computer Equipment", "Lodging", "Meals - Individual", "Meals - Team", "Office Supplies", "Travel - Other" (avoid "Software").
- "Meals - Individual", "Lodging", "Travel - Other" MUST carry the trip_id of an existing trip of the skeleton. Other types: no trip_id.
- Limits that make ONE receipt fail (do not exceed on a single receipt): gift to one named recipient > $50; an unnamed gift >= $10 (name the recipient in gift_for); computer_accessory unit price > $200 without pre_approval_ref ("PA-2026-NNNN"); non-itemized total > $75; meals per person per day > $75 (APAC $60); team meal total > $150 (attendees must be >= 2); health_otc > $25 per trip; personal_care/clothing > $150; NO alcohol, tobacco, gambling, gift cards, personal electronics lines; no receipt between 00:00 and 05:59.
- Use realistic merchant category codes (mcc) such as 5812 restaurants, 5814 cafes, 4121 taxis, 4111 transit, 7011 hotels, 4511 airlines, 7512 car rental, 7523 parking, 5943 stationery, 5111 office supplies, 5045 computers, 5992 florists, 5947 gift shops, 5942 bookstores. Avoid 5732 and 5999.
- Line categories allowed: """ + CATS + """. Airline/lounge/seat fees use "other"; rail uses "ground_transport"; hotel rooms "lodging".
- attendee_count: integer >= 2 for Meals - Team and Client Entertainment, 1 for Meals - Individual, null otherwise.
- Merchants must fit what they sell, prices must be realistic, merchants fictional, descriptions natively written in the history's language (mix in a few English product names is fine). All descriptions inside one history must differ unless the mechanism itself is the repetition."""

def prompt(sk, domain=None, mech=None, decoy=None, ext=None):
    L = [f"You are writing synthetic but realistic expense data for testing a fraud-review system. Write ONE employee-month ({sk['persona']}, entity {sk['entity']}, writing language: {sk['language']}) as JSON. Reply with ONLY the JSON object, no prose.", "", FACTS, "",
         f"SKELETON (fixed by code, you must keep it; month {sk['month']:02d}/2026, {sk['n']} receipts). Slots:"]
    for s in sk["slots"]:
        L.append(f"- {s['slot']} | {s['date']} ({'weekend' if s['weekend'] else 'weekday'}) | {s['type']} | " + (f"trip {s['trip_id']} ({s['trip_nights']} nights)" if s['trip_id'] else "no trip"))
    if sk["class"] == "fraud":
        task = (f"TASK: you play a dishonest employee. Build ONE evasion scheme of the standard category «{ext[0]}»: {ext[1]}. Make it your own concrete scenario. EACH receipt must pass every per-receipt rule listed above, yet the pattern across receipts would make a careful human auditor suspicious."
                if ext else f"TASK: you play a dishonest employee. Invent ONE NEW evasion scheme in the domain «{domain}» using the mechanism family «{mech}»: EACH receipt passes every per-receipt rule, yet the pattern across receipts would make a careful human auditor suspicious (double-claiming, circumvention of a limit, hidden personal spend, claims that do not fit the trip/relationship/headcount/items).")
        L += ["", task,
              f"Choose exactly {sk['planted_k']} slots to carry the scheme (mark them \"planted\": true). For planted slots you MAY change date and expense type freely (keep trip rules), BUT exactly {sk['planted_weekend']} of the planted receipts must fall on a Saturday or Sunday. All other slots must keep their skeleton date, type and trip exactly and must look like ordinary honest spending.",
              ("" if ext else f"Do NOT reuse these already-used schemes or paraphrase them: {USED}.")]
    else:
        L += ["", "TASK: write an HONEST, ordinary month: every slot keeps its skeleton date/type/trip; \"planted\" is false everywhere; scheme is \"clean\"."]
        if decoy: L.append(f"Hard-negative requirement: include ONE innocent coincidence that superficially resembles a suspicious pattern but is fully legitimate: {decoy}. Nothing else may look odd.")
    L += ["", "OUTPUT JSON schema:", '{"scheme": "<snake_case or clean>", "reason": "<one sentence: why the pattern is suspicious, or ordinary month>", "receipts": [ {"slot": "S01", "planted": false, "merchant_name": "...", "mcc": "5812", "mcc_description": "...", "datetime": "YYYY-MM-DDTHH:MM:SS", "expense_type": "...", "trip_id": null, "attendee_count": null, "pre_approval_ref": null, "itemized": true, "lines": [ {"description_raw": "...", "quantity": 1, "unit_price": 12.5, "category": "food_beverage"} ], "gift_for": {"1": ["client", "Full Name"]} } ] }',
          "gift_for maps the 1-based line number to [kind, name] and appears only on gift lines; kind must ALWAYS be the literal string \"client\" (never colleague/employee/official). Write one object per slot (exactly the skeleton's slots, in order). The history reason must refer only to what the receipts really contain."]
    return "\n".join(L)

DECOYS = ["a single one-off gift to one named client (a real thank-you)", "a real business trip with a hotel, taxis and local meals", "the same cafe visited several times because it is next to the office", "two purchases at the same stationery shop a few days apart for different needs", "one expensive but fully pre-approved monitor with a valid approval reference", "a team lunch exactly during a real project week", "a taxi ride home after a late client dinner (before midnight)", "a repeated monthly office-supply restock of the same item at the same shop"]

def extract_json(text):
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    i = text.find("{")
    while i != -1:
        depth = 0
        for j in range(i, len(text)):
            depth += text[j] == "{"; depth -= text[j] == "}"
            if depth == 0:
                try: return json.loads(text[i:j + 1])
                except Exception: break
        i = text.find("{", i + 1)
    return None

def build(sk, out, hid):
    """Turn the author's JSON into a red-team style history; return (history, errors)."""
    err = []; by = {s["slot"]: s for s in sk["slots"]}; recs = out.get("receipts") or []
    if [r.get("slot") for r in recs] != [s["slot"] for s in sk["slots"]]: err.append("receipts must be exactly the skeleton slots S01.. in order, one object per slot")
    planted = [r for r in recs if r.get("planted")]
    if sk["class"] == "fraud":
        if len(planted) != sk["planted_k"]: err.append(f"need exactly {sk['planted_k']} planted receipts, got {len(planted)}")
        def wk(r):
            try: return datetime.datetime.fromisoformat(r["datetime"]).weekday() >= 5
            except Exception: return False
        if sum(wk(r) for r in planted) != sk["planted_weekend"]: err.append(f"exactly {sk['planted_weekend']} planted receipts must be on a Saturday/Sunday")
    elif planted: err.append("clean history must have no planted receipts")
    trips = {s["trip_id"]: s["trip_nights"] for s in sk["slots"] if s["trip_id"]}; receipts = []; seen = set()
    for i, r in enumerate(recs, 1):
        s = by.get(r.get("slot"))
        if not s: err.append(f"unknown slot {r.get('slot')}"); continue
        try: dt = datetime.datetime.fromisoformat(r["datetime"])
        except Exception: err.append(f"{s['slot']}: bad datetime"); continue
        if not r.get("planted"):
            if r["datetime"][:10] != s["date"]: err.append(f"{s['slot']}: non-planted receipt must keep date {s['date']}")
            if r.get("expense_type") != s["type"]: err.append(f"{s['slot']}: non-planted receipt must keep type {s['type']}")
            if (r.get("trip_id") or None) != s["trip_id"]: err.append(f"{s['slot']}: non-planted receipt must keep trip {s['trip_id']}")
        if dt.hour < 6: err.append(f"{s['slot']}: time must be between 06:00 and 23:59")
        if dt.month != sk["month"] or dt.year != 2026: err.append(f"{s['slot']}: date outside the month")
        tid = r.get("trip_id") or None
        if tid and tid not in trips: err.append(f"{s['slot']}: unknown trip_id {tid}")
        rid = f"{hid}-R{i:02d}"; lines = []; gf = {}
        for k, l in enumerate(r.get("lines") or [], 1):
            try: q = int(l["quantity"]); up = round(float(l["unit_price"]), 2); amt = round(q * up, 2)
            except Exception: err.append(f"{s['slot']}: bad line numbers"); continue
            if l.get("category") not in CATS.replace(" ", "").split(","): err.append(f"{s['slot']}: bad category {l.get('category')}")
            if amt <= 0: err.append(f"{s['slot']}: non-positive amount")
            lid = f"{rid}-L{k}"; lines.append({"line_id": lid, "description_raw": str(l.get("description_raw", ""))[:200], "language": sk["language"], "quantity": q, "unit_price": up, "amount": amt, "amount_usd": amt, "category": l.get("category")})
            if str(k) in (r.get("gift_for") or {}): v = r["gift_for"][str(k)]; gf[lid] = [v[0], v[1]]
        if not lines: err.append(f"{s['slot']}: no lines"); continue
        total = round(sum(l["amount"] for l in lines), 2); descs = [l["description_raw"] for l in lines]
        if len(set(descs)) != len(descs): err.append(f"{s['slot']}: duplicate line descriptions inside one receipt")
        receipts.append({"receipt_id": rid, "employee_id": f"E-{random.Random(hid).randint(1000, 9999)}", "employee_country": sk["country"], "entity": sk["entity"], "submitted_expense_type": r.get("expense_type"), "merchant_name": r.get("merchant_name"),
                         "mcc": str(r.get("mcc")), "mcc_description": r.get("mcc_description") or "", "transaction_datetime": dt.strftime("%Y-%m-%dT%H:%M:%S"), "currency": "USD", "fx_rate_to_usd": 1, "total_amount": total, "total_amount_usd": total,
                         "attendee_count": r.get("attendee_count"), "trip_id": tid, "trip_nights": trips.get(tid) if tid else None, "pre_approval_ref": r.get("pre_approval_ref"), "itemized": bool(r.get("itemized", True)), "line_items": lines,
                         "planted": bool(r.get("planted")), **({"gift_for": gf} if gf else {})})
    h = {"history_id": hid, "scheme": out.get("scheme") if sk["class"] == "fraud" else "clean", "reason": out.get("reason", ""), "language": sk["language"], "class": sk["class"], "skeleton": {k: v for k, v in sk.items() if k != "slots"}, "receipts": receipts}
    return h, err

def engine_errors(h):
    try:
        res = ea.evaluate_history(h)
    except Exception as e: return [f"engine error: {type(e).__name__}: {e}"]
    return [f"{rid}: engine disposition {x.disposition}: " + ", ".join(f"{a}({b}): {d}" for a, b, d in x.fired) for rid, x in res.items() if x.disposition != "pass"]

STOP = {"flag": False}
def call(model, text, timeout=420):
    if STOP["flag"]: raise RuntimeError("STOPPED: provider limit or balance error seen earlier")
    guard = "IMPORTANT: do NOT use any tool, do NOT write files, do NOT run commands or scripts, do NOT read any file. Answer directly in your message with the JSON object only.\n\n"
    sandbox = tempfile.mkdtemp(prefix="oc_sandbox_")          # empty working directory: nothing of the project is reachable by default
    p = subprocess.run(["opencode", "run", "-m", model, guard + text], capture_output=True, text=True, timeout=timeout, cwd=sandbox)
    out = (p.stdout or "") + (p.stderr or "")
    if "{" not in out or extract_json(out) is None:             # fallback: the model wrote its JSON to a file inside the sandbox
        for fp in sorted(glob.glob(sandbox + "/**/*.json", recursive=True)):
            try: out += "\n" + open(fp).read()
            except Exception: pass
    if re.search(r"insufficient[- ]balance|rate limited|invalid API key|Model unavailable|not included in your subscription", out[:600], re.I) and len(out) < 600:
        STOP["flag"] = True; raise RuntimeError("PROVIDER: " + re.sub(r"\x1b\[[0-9;]*m", "", out).strip()[:160])
    return out

def one(args, idx):
    ext = TAXONOMY[(idx + args.seed) % len(TAXONOMY)] if args.ext else None
    rng = random.Random(args.seed * 1000 + idx); sk = SK.sample(rng, args.cls); hid = f"{args.family[:2].upper()}{args.cls[0].upper()}{args.seed:03d}{idx:03d}"
    domain, mech, decoy = DOMAINS[(idx + args.seed) % len(DOMAINS)], MECHS[(idx * 3 + args.seed) % len(MECHS)], DECOYS[(idx + args.seed) % len(DECOYS)]
    base = prompt(sk, domain, mech, decoy, ext); text = base; log = []
    for attempt in range(1 + args.retries):
        try: raw = call(args.model, text)
        except Exception as e: log.append(f"call failed: {e}"); break
        out = extract_json(raw)
        if not out: log.append("no JSON in the answer"); text = base + "\n\nYour previous answer had no valid JSON. Reply with ONLY the JSON object."; continue
        h, err = build(sk, out, hid)
        if not err: err = engine_errors(h)
        if not err:
            h["meta"] = {"model": args.model, "family": args.family, "domain": (ext[0] if ext else domain), "mechanism": (ext[1] if ext else mech), "decoy": decoy if args.cls == "clean" else None, "attempts": attempt + 1}; return h, log
        log.append("; ".join(err)[:600]); text = base + "\n\nYour previous attempt FAILED these checks, fix them and answer with the full JSON again:\n- " + "\n- ".join(err[:12])
    return None, log

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--model", required=True); ap.add_argument("--family", required=True); ap.add_argument("--cls", choices=["fraud", "clean"], required=True)
    ap.add_argument("--n", type=int, default=4); ap.add_argument("--seed", type=int, default=1); ap.add_argument("--out", default="out"); ap.add_argument("--retries", type=int, default=2); ap.add_argument("--workers", type=int, default=3); ap.add_argument("--ext", action="store_true", help="use the external fraud taxonomy (for the blind exam E6)")
    a = ap.parse_args(); Path(a.out).mkdir(exist_ok=True); ok = []; fails = []
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for h, log in ex.map(lambda i: one(a, i), range(a.n)):
            (ok if h else fails).append(h or log)
    fn = Path(a.out) / f"{a.family}_{a.cls}_s{a.seed}.json"; json.dump(ok, open(fn, "w"), ensure_ascii=False)
    print(f"{a.family}/{a.cls}: {len(ok)}/{a.n} valid; attempts: {[h['meta']['attempts'] for h in ok]}"); [print("FAIL:", f[-1][:300] if f else "?") for f in fails[:3]]
