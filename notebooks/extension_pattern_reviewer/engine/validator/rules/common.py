"""Field parsing and definitions shared by the rule families.

Bad data raises ValueError (missing keys KeyError), never a silent zero. Meal definitions are
MEAL-01's, which REG-02 and REG-03 reuse ("defined as in MEAL-01").
"""
from decimal import Decimal
from fractions import Fraction

MEAL_TYPES = ("Meals - Individual", "Meals - Team", "Client Entertainment")
FOOD_OR_DRINK = frozenset({"food_beverage", "alcohol"})  # what "contains food or drink" looks for
MEAL_SPEND = FOOD_OR_DRINK | {"service_fee"}             # food, drink and gratuity lines


def money(value, label: str) -> Decimal:
    """A finite number as Decimal. bool, str, None and NaN are bad data, never zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{label} must be a number, got {value!r}")
    d = Decimal(str(value))
    if not d.is_finite():
        raise ValueError(f"{label} must be finite, got {value!r}")
    return d


def attendees(receipt: dict) -> int | None:
    n = receipt["attendee_count"]
    if n is not None and (type(n) is not int or n < 1):
        raise ValueError(f"{receipt.get('receipt_id')}: attendee_count must be a positive int or None, got {n!r}")
    return n


def currency(receipt: dict) -> str:
    """The ISO code, so ' usd' and 'USD' are the same currency."""
    cur = receipt["currency"]
    if not isinstance(cur, str) or not cur.strip():
        raise ValueError(f"{receipt.get('receipt_id')}: currency must be a code, got {cur!r}")
    return cur.strip().upper()


def mcc_code(receipt: dict) -> str | None:
    """The MCC as a stripped string (" 5921" and 5921 are "5921"), or None when none is recorded."""
    code = str(receipt.get("mcc")).strip()
    return None if code in ("", "None") else code


def itemized(receipt: dict) -> bool:
    if type(receipt["itemized"]) is not bool:
        raise ValueError(f"itemized must be a bool, got {receipt['itemized']!r}")
    return receipt["itemized"]


def day_key(receipt: dict) -> tuple[str, str]:
    """(employee_id, calendar date as written): the MEAL-01 day. A receipt missing either is a day of
    its own, never pooled with anyone else's."""
    emp, when = receipt.get("employee_id"), receipt.get("transaction_datetime")
    if emp is None or not isinstance(when, str) or not when.strip():
        return ("receipt", receipt["receipt_id"])
    return (emp, when[:10])


def meal_per_person(receipt: dict, categories: dict[str, str]) -> Fraction | None:
    """MEAL-01's per-person meal spend in USD, exact, or None when this is not a meal receipt.

    Meal receipt: a declared meal type that contains food or drink, or is not itemized. Spend: its
    food, drink and gratuity lines, or the full USD total when not itemized. Divided by
    attendee_count, or by 1 when none is recorded.
    """
    cat = {li["line_id"]: categories[li["line_id"]] for li in receipt["line_items"]}  # a missing line raises KeyError
    whole = not itemized(receipt)
    if receipt["submitted_expense_type"] not in MEAL_TYPES or not (whole or FOOD_OR_DRINK & set(cat.values())):
        return None
    if whole:
        spend = money(receipt["total_amount_usd"], "total_amount_usd")
    else:
        spend = sum((money(li["amount_usd"], li["line_id"]) for li in receipt["line_items"]
                     if cat[li["line_id"]] in MEAL_SPEND), Decimal(0))
    return Fraction(spend) / (attendees(receipt) or 1)
