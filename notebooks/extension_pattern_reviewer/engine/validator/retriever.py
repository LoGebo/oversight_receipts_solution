"""Policy retriever (component 3): the rules that could apply to a receipt, from its items, MCC and metadata.

No vector DB and no model: a plain table of applicability predicates, one per rule, each read from the
scope sentence of that rule in data/policy-docs. Deliberately GENEROUS (recall over precision): a
predicate asks whether the rule's subject is present at all (a category, an MCC tier, an entity, an
expense type...), never whether the rule is broken; that is the engine's job.
The engine still evaluates every rule (they are cheap) and gives a receipt whose fired rule is not a
candidate an ERR-retriever review signal, so a predicate that is too narrow shows instead of hiding a violation.
"""
from validator.rules import merchant, timing
from validator.rules.common import MEAL_TYPES
from validator.rules.documentation import EXTENSIONS

GIFT_CATEGORIES = {"gift", "gift_card", "jewelry"}
BAR_OR_LIQUOR_MCC = {"5813", "5921"}


def _cur(receipt: dict) -> str:
    return str(receipt.get("currency") or "").strip().upper()


def candidate_rules(receipt: dict, categories: dict[str, str],
                    gift_for: dict | None = None) -> dict[str, str]:
    """rule_id -> why it is a candidate. `categories`: line_id -> engine category (a missing line counts
    as no category); `gift_for`: line_id -> (kind, name) for lines whose text names a recipient."""
    cats = {categories.get(li["line_id"]) for li in receipt["line_items"]}
    named = {li["line_id"] for li in receipt["line_items"]} & set(gift_for or ())
    mcc, entity, kind = str(receipt.get("mcc")).strip(), receipt.get("entity"), receipt.get("submitted_expense_type")
    meal = kind in MEAL_TYPES
    has = cats.__contains__
    alc = has("alcohol") or mcc in BAR_OR_LIQUOR_MCC
    gifty = kind == "Client Gifts" or bool(cats & GIFT_CATEGORIES) or bool(named)
    when = receipt.get("transaction_datetime")
    table = {
        "ALC-01": (alc, "alcohol line, or a bar or liquor store"),
        "ALC-02": (alc, "alcohol line, or a bar or liquor store"),
        "ALC-03": (alc, "alcohol line, or a bar or liquor store"),
        "REG-01": (has("alcohol") and entity == "APAC", "alcohol line, APAC employee"),
        "MCC-01": (mcc in merchant.HIGH, f"MCC {mcc} is in the high-risk list"),
        "MCC-02": (mcc in merchant.MEDIUM, f"MCC {mcc} is in the medium-risk list"),
        "TECH-01": (has("personal_electronics") or mcc == "5732", "personal electronics line or electronics store"),
        "TECH-02": (has("computer_accessory"), "computer accessory line"),
        "TECH-03": (has("mobile_handset"), "mobile handset line"),
        "TECH-04": (has("software_subscription"), "software subscription line"),
        "ENT-01": (has("entertainment_venue"), "entertainment venue line"),
        "ENT-02": (has("gambling") or mcc == "7995", "gambling line or betting merchant"),
        "PERS-01": (has("personal_care") or has("clothing"), "personal care or clothing line (shared allowance)"),
        "PERS-02": (has("personal_care") or has("clothing"), "personal care or clothing line (shared allowance)"),
        "PERS-03": (has("tobacco") or mcc == "5993", "tobacco line or tobacco store"),
        "HOUSE-01": (has("household_goods"), "household goods line"),
        "LAUNDRY-01": (has("laundry_service"), "laundry line"),
        "HEALTH-01": (has("health_otc") or has("prescription_medication"), "OTC or prescription medication line"),
        "DOC-01": (receipt.get("itemized") is not True, "receipt is not itemized"),
        "DOC-02": (True, "every receipt needs a merchant, date and total"),
        "DOC-03": (bool({EXTENSIONS.get(c, c) for c in cats} - {"service_fee", "other"}),
                   f"declared {kind!r} vs the line categories"),
        "DOC-04": (_cur(receipt) != "USD", f"currency {_cur(receipt) or 'missing'} is not USD"),
        "GIFT-01": (gifty, "declared Client Gifts, a gift-type line, or a line naming a recipient"),
        "GIFT-02": (has("gift_card"), "gift card line"),
        "GIFT-03": (gifty, "declared Client Gifts, a gift-type line, or a line naming a recipient"),
        "GIFT-04": (gifty, "declared Client Gifts, a gift-type line, or a line naming a recipient"),
        "MEAL-01": (meal, f"declared meal type {kind!r}"),
        "MEAL-02": (meal, f"declared meal type {kind!r}"),
        "REG-02": (meal and entity == "APAC", "meal, APAC employee"),
        "REG-03": (meal and entity == "EMEA", "meal, EMEA employee"),
        "REG-04": (entity == "EMEA", "EMEA employee"),
        "REG-05": (receipt.get("fx_rate_to_usd") is not None, "a conversion rate is recorded"),
        "TIME-01": (isinstance(when, str) and bool(when.strip()), "a transaction time is recorded"),
        "TIME-02": (kind in timing.TRAVEL_TYPES, f"declared {kind!r}, an individual travel expense type"),
        "TIME-03": (meal or receipt.get("itemized") is not True or bool(named),
                    "a meal, non-itemized or named-gift receipt can be split with the same merchant's others that day"),
        "TIME-04": (receipt.get("trip_id") is not None, "linked to a trip"),
        "EXC-03": (True, "any classified line may be uncertain"),
    }
    return {rule: why for rule, (applies, why) in table.items() if applies}
