import random

import pytest

from validator import retriever
from validator.classifier import CATEGORIES, classify
from validator.engine import EXPECTED, run_engine
from validator.gold import load_gold
from validator.loader import load_receipts
from validator.retriever import candidate_rules
from validator.rules import alcohol, documentation, gifts, merchant, regional

RECEIPTS = load_receipts()
GOV_RCP022 = {"RCP-022-L1": ("government_official", "R. Delgado"), "RCP-022-L2": ("government_official", "R. Delgado")}


class _NoNetwork:
    @property
    def messages(self):
        raise RuntimeError("cache miss")


def fired(result):
    return {c.rule_id for c in result.checks if c.status == "fired" and not c.rule_id.startswith("ERR-")}


def assert_recall(results):
    for res in results.values():
        assert fired(res) <= res.considered.keys(), res.receipt_id
        assert res.considered.keys() <= EXPECTED


def test_recall_on_the_real_receipts_with_hand_labelled_categories():
    cats = {lid: lab["category"] for g in load_gold().values() for lid, lab in g["line_labels"].items()}
    assert_recall(run_engine(RECEIPTS, cats, gift_for=GOV_RCP022))


def test_recall_on_the_real_receipts_with_the_committed_cache():
    c = classify(RECEIPTS, client=_NoNetwork())
    assert not c.meta["failures"], c.meta["failures"]
    assert_recall(run_engine(RECEIPTS, c.categories, gift_for=c.gift_for, uncertain=c.uncertain))


BASE = {"receipt_id": "T", "mcc": "5812", "entity": "GLOBAL", "submitted_expense_type": "Lodging", "currency": "USD",
        "itemized": True, "fx_rate_to_usd": None, "line_items": [{"line_id": "T-L1"}]}
MEAL, ALWAYS = {"submitted_expense_type": "Meals - Team"}, None
CASES = {  # rule -> (fields, category) that make it a candidate, and that do not (None: always a candidate)
    **{r: (({}, "alcohol"), ({}, "food_beverage")) for r in ("ALC-01", "ALC-02", "ALC-03")},
    "REG-01": (({"entity": "APAC"}, "alcohol"), ({}, "alcohol")),
    "MCC-01": (({"mcc": "5921"}, "food_beverage"), ({}, "food_beverage")),
    "MCC-02": (({"mcc": " 5411"}, "food_beverage"), ({}, "food_beverage")),
    **{r: (({}, c), ({}, "food_beverage")) for r, c in (
        ("TECH-01", "personal_electronics"), ("TECH-02", "computer_accessory"), ("TECH-03", "mobile_handset"),
        ("TECH-04", "software_subscription"), ("ENT-01", "entertainment_venue"), ("ENT-02", "gambling"),
        ("PERS-01", "personal_care"), ("PERS-02", "clothing"), ("PERS-03", "tobacco"), ("HOUSE-01", "household_goods"),
        ("LAUNDRY-01", "laundry_service"), ("HEALTH-01", "health_otc"), ("GIFT-02", "gift_card"),
        ("GIFT-03", "gift"), ("GIFT-04", "jewelry"))},
    "GIFT-01": (({"submitted_expense_type": "Client Gifts"}, "food_beverage"), ({}, "food_beverage")),
    "DOC-01": (({"itemized": False}, "other"), ({}, "other")),
    "DOC-02": (({}, "other"), ALWAYS),
    "DOC-03": (({}, "food_beverage"), ({}, "service_fee")),
    "DOC-04": (({"currency": "eur"}, "food_beverage"), ({"currency": " usd"}, "food_beverage")),
    "MEAL-01": ((MEAL, "food_beverage"), ({}, "food_beverage")),
    "MEAL-02": ((MEAL, "food_beverage"), ({}, "food_beverage")),
    "REG-02": (({**MEAL, "entity": "APAC"}, "food_beverage"), (MEAL, "food_beverage")),
    "REG-03": (({**MEAL, "entity": "EMEA"}, "food_beverage"), (MEAL, "food_beverage")),
    "REG-04": (({"entity": "EMEA"}, "food_beverage"), ({}, "food_beverage")),
    "REG-05": (({"fx_rate_to_usd": 1.08}, "food_beverage"), ({}, "food_beverage")),
    "TIME-01": (({"transaction_datetime": "2026-05-07T02:14:00"}, "other"), ({"transaction_datetime": " "}, "other")),
    "TIME-02": (({}, "other"), ({"submitted_expense_type": "Software"}, "other")),
    "TIME-03": (({"itemized": False}, "other"), ({}, "other")),
    "TIME-04": (({"trip_id": "TRIP-1"}, "other"), ({"trip_id": None}, "other")),
    "EXC-03": (({}, "other"), ALWAYS),
}


def test_every_engine_rule_has_a_case():
    assert CASES.keys() == EXPECTED


@pytest.mark.parametrize("rule", sorted(CASES))
def test_candidate_and_non_candidate(rule):
    yes, no = CASES[rule]
    assert rule in candidate_rules({**BASE, **yes[0]}, {"T-L1": yes[1]})
    if no is not None:
        assert rule not in candidate_rules({**BASE, **no[0]}, {"T-L1": no[1]})


def test_a_named_recipient_makes_the_gift_rules_candidates():
    hook = {"T-L1": ("government_official", None)}
    assert {"GIFT-01", "GIFT-03", "GIFT-04"} <= candidate_rules(BASE, {"T-L1": "food_beverage"}, hook).keys()
    assert not {"GIFT-01", "GIFT-03", "GIFT-04"} & candidate_rules(BASE, {"T-L1": "food_beverage"}, {"X-L1": hook["T-L1"]}).keys()


def test_a_prescription_line_makes_health01_a_candidate():
    assert "HEALTH-01" in candidate_rules(BASE, {"T-L1": "prescription_medication"})


def test_bad_data_never_crashes_the_retriever():
    assert "EXC-03" in candidate_rules({"line_items": [{"line_id": "T-L1"}], "mcc": None, "currency": None}, {})


def test_engine_reports_a_fired_rule_the_retriever_missed(monkeypatch):
    monkeypatch.setattr(retriever, "candidate_rules", lambda *_: {})
    cats = {"RCP-026-L1": "computer_accessory", "RCP-026-L2": "computer_accessory"}
    res = run_engine([r for r in RECEIPTS if r["receipt_id"] == "RCP-026"], cats)["RCP-026"]
    assert "missed rule TECH-02" in res.error and res.disposition == "flag"


@pytest.mark.parametrize("mcc", sorted(retriever.BAR_OR_LIQUOR_MCC))
def test_a_bar_or_liquor_store_makes_the_alcohol_rules_candidates_without_an_alcohol_line(mcc):
    assert {"ALC-01", "ALC-02", "ALC-03"} <= candidate_rules({**BASE, "mcc": mcc}, {"T-L1": "food_beverage"}).keys()
    rcp011 = next(r for r in RECEIPTS if r["receipt_id"] == "RCP-011")  # liquor store; both lines filed as food here
    res = run_engine([{**rcp011, "mcc": mcc}], {"RCP-011-L1": "food_beverage", "RCP-011-L2": "food_beverage"})["RCP-011"]
    assert {"ALC-01", "ALC-02", "ALC-03"} <= res.considered.keys()


# Property: synthetic receipts built from the rule modules' own constants; every fired rule is a candidate.
ENGINE_CATEGORIES = sorted(set(CATEGORIES) | set(documentation.EXTENSIONS))
MCCS = sorted(merchant.HIGH | merchant.MEDIUM | alcohol.ON_PREMISES_MCC | {"4121", "5045", "5999"})
EXPENSE_TYPES = sorted(documentation.COVERS)
PLACES = [("GLOBAL", "US")] + [(e, c) for e, cs in regional.COUNTRIES.items() for c in sorted(cs)]


def _synthetic(rng: random.Random, base: dict) -> tuple[dict, dict, dict]:
    entity, country = rng.choice(PLACES)
    cur, rate = rng.choice([("USD", None), ("EUR", 1.08), ("EUR", None), ("JPY", 0.0067)])
    r = {**base, "mcc": rng.choice(MCCS), "entity": entity, "employee_country": country, "currency": cur,
         "fx_rate_to_usd": rate, "submitted_expense_type": rng.choice(EXPENSE_TYPES), "itemized": rng.random() < 0.8,
         "attendee_count": rng.choice([None, 1, 2, 5]), "trip_id": rng.choice([None, "TRIP-X"]),
         "trip_nights": rng.choice([None, 2, 5]), "pre_approval_ref": rng.choice([None, "PA-2026-0001"]),
         "merchant_name": base["merchant_name"] if rng.random() < 0.9 else None}
    cats = {li["line_id"]: rng.choice(ENGINE_CATEGORIES) for li in r["line_items"]}
    hook = {lid: (rng.choice(gifts.RECIPIENT_KINDS), rng.choice([None, "A. Name"])) for lid in cats if rng.random() < 0.2}
    return r, cats, hook


@pytest.mark.parametrize("seed", range(40))
def test_fired_rules_are_always_candidates(seed):
    rng = random.Random(seed)
    for _ in range(10):
        batch, cats, hook, unsure = [], {}, {}, {}
        for base in rng.sample(RECEIPTS, 3):
            r, c, h = _synthetic(rng, base)
            batch.append(r)
            cats.update(c)
            hook.update(h)
            if r["itemized"] and rng.random() < 0.2:
                unsure[r["receipt_id"]] = {r["line_items"][0]["line_id"]}
        results = run_engine(batch, cats, gift_for=hook, uncertain=unsure)
        assert_recall(results)
        assert not any("ERR-retriever" in (r.error or "") for r in results.values())
