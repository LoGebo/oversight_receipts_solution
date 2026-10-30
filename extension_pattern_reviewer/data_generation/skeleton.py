"""Code-controlled skeleton of one employee-month. Fraud and clean histories come from THE SAME sampler, so surface features
(number of receipts, weekend fraction, trips, type mix, month, language, entity) have the same distribution in both classes.
The LLM author only writes text (merchants, descriptions, prices) and, for fraud, inserts the mechanism into the planted slots."""
import random, datetime
MONTHS = [3, 4, 5, 6, 7, 8, 9, 10]            # 2026; more than one month on purpose (all earlier data was May)
PERSONAS = {
    "traveling sales rep": {"Meals - Individual": 3, "Travel - Other": 2, "Lodging": 2, "Client Entertainment": 1, "Client Gifts": 1, "Office Supplies": 1, "Meals - Team": 1},
    "office engineer": {"Office Supplies": 3, "Computer Equipment": 2, "Meals - Team": 2, "Meals - Individual": 1, "Travel - Other": 1},
    "executive assistant": {"Office Supplies": 3, "Meals - Team": 2, "Client Gifts": 1, "Travel - Other": 2, "Client Entertainment": 1},
    "team manager": {"Meals - Team": 3, "Client Entertainment": 2, "Computer Equipment": 1, "Office Supplies": 2, "Travel - Other": 1, "Lodging": 1},
    "field consultant": {"Meals - Individual": 3, "Travel - Other": 3, "Lodging": 2, "Office Supplies": 1, "Computer Equipment": 1},
    "marketing coordinator": {"Client Gifts": 2, "Client Entertainment": 2, "Meals - Team": 2, "Office Supplies": 2, "Travel - Other": 1},
}
LANGS = ["en", "es", "fr", "de", "pt", "ja"]
P_WEEKEND = 0.12                                 # per-receipt probability, SAME for fraud and clean
def _days(year, month):
    d = datetime.date(year, month, 1); out = []
    while d.month == month: out.append(d); d += datetime.timedelta(days=1)
    return out
def sample(rng, cls):
    month = rng.choice(MONTHS); persona = rng.choice(list(PERSONAS)); weights = PERSONAS[persona]
    entity = "APAC" if rng.random() < .18 else "GLOBAL"; country = "JP" if entity == "APAC" else "US"; lang = rng.choice(LANGS if entity == "GLOBAL" else ["ja", "en"])
    days = _days(2026, month); weekdays = [d for d in days if d.weekday() < 5]; weekends = [d for d in days if d.weekday() >= 5]
    n = rng.randint(8, 13); slots = []; sid = 0
    def add(t, d, trip=None, nights=None, hour=None):
        nonlocal sid; sid += 1
        slots.append({"slot": f"S{sid:02d}", "type": t, "date": d.isoformat(), "weekend": d.weekday() >= 5, "trip_id": trip, "trip_nights": nights, "planted": False})
    # trips (same probabilities in both classes)
    ntrips = rng.choices([0, 1, 2], [.45, .42, .13])[0]
    for k in range(ntrips):
        nights = rng.randint(1, 4); start = rng.choice(weekdays[:-6]); tid = f"TRIP-{rng.randint(1000, 9999)}"; span = [start + datetime.timedelta(days=i) for i in range(nights + 1)]
        span = [d for d in span if d.month == month]
        add("Lodging", span[0], tid, nights); add("Travel - Other", span[0], tid, nights)
        if rng.random() < .6 and len(span) > 1: add("Travel - Other", span[-1], tid, nights)
        for _ in range(rng.choice([0, 1, 2])): add("Meals - Individual", rng.choice(span), tid, nights)
    types = list(weights); w = [weights[t] for t in types]
    while len(slots) < n:
        t = rng.choices(types, w)[0]
        if t in ("Lodging", "Travel - Other", "Meals - Individual"): t = rng.choices(["Office Supplies", "Meals - Team", "Computer Equipment"], [3, 2, 1])[0]   # trip-bound types only inside trips
        d = rng.choice(weekends) if rng.random() < P_WEEKEND else rng.choice(weekdays); add(t, d)
    slots = slots[:max(n, len(slots))]; slots.sort(key=lambda s: s["date"])
    for i, s in enumerate(slots, 1): s["slot"] = f"S{i:02d}"
    sk = {"class": cls, "month": month, "persona": persona, "entity": entity, "country": country, "language": lang, "n": len(slots), "slots": slots}
    if cls == "fraud":
        k = rng.choice([2, 3, 4, 5]); pw = sum(rng.random() < P_WEEKEND for _ in range(k))        # planted weekend count drawn from the same per-receipt law
        sk["planted_k"] = k; sk["planted_weekend"] = pw
    return sk
