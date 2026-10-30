"""Gift rules: GIFT-01 (client cap, medium), GIFT-02 (gift cards, high), GIFT-03 (employee gifts, medium),
GIFT-04 (government officials, critical, routed to Compliance).

Per receipt, not cross-receipt: the GIFT-01 occasion is one receipt, and no rule caps per year.

What makes a line a gift (policy): the receipt is declared "Client Gifts" (`submitted_expense_type`)
OR the line names who it is for. Category alone does not: a bracelet (`jewelry`) is a gift when it
is for someone, and a greeting card (`gift`) on an Office Supplies receipt naming nobody is not.
Food, drink and gratuities (food_beverage, alcohol, service_fee) are never gifts: at a meal the meal
rules govern them, and EXC-04 never cites a service fee.

Limit: who a line is for (client, employee, government official, and the name) lives only in free
text (`description_raw`); no structured field holds it. That comes from the `is_gift_for` hook,
filled by the classifier (Classification.gift_for): line_id -> (kind, name or None), kind in RECIPIENT_KINDS.
Name it whenever the recipient is named anywhere on the expense. A line left out names nobody.
Without the hook: GIFT-02 still works (category only); GIFT-01 works on "Client Gifts" receipts,
treating every line as an unnamed client gift; GIFT-03 and GIFT-04 can never fire.
EXC-02: no gift rule asks for a reference, so `pre_approval_ref` waives nothing here.
Limit: a gift card for an employee is reported under GIFT-02 alone, not GIFT-03 as well.
Limit: GIFT-04 "is routed to Compliance immediately"; the report has no routing field, so the routing is
the critical severity itself (approval-and-exception-handling.md: critical is "Routed to Compliance
immediately"), and nothing here sends it anywhere.
Limit: on a "Client Gifts" receipt every line outside NOT_GIFTS is a gift line, so a tax line (if
the classifier files it as `other`) adds to the recipient's GIFT-01 total.
"""
from collections import defaultdict
from decimal import Decimal

from validator.check import Check
from validator.rules.common import money

CAP = Decimal("50")            # GIFT-01: USD per recipient per receipt; strictly above fires
NAME_FROM = Decimal("10")      # GIFT-01: an unnamed gift of $10 or more (inclusive) fires
NOT_GIFTS = {"food_beverage", "alcohol", "service_fee"}
RECIPIENT_KINDS = ("client", "employee", "government_official")  # client covers prospects
RULE_IDS = ("GIFT-01", "GIFT-02", "GIFT-03", "GIFT-04")


def _gift01(lines: list[dict], names: dict[str, str | None], replaced: bool) -> Check:
    if not lines:
        if replaced:
            return Check("GIFT-01", "superseded", detail="every gift line is for a government official: GIFT-04 replaces it")
        return Check("GIFT-01", "not_applicable", detail="no client gift line")
    groups, unnamed = defaultdict(list), []
    for li in lines:
        name = (names[li["line_id"]] or "").strip().casefold()
        if name:
            groups[name].append(li)
        else:
            groups[li["line_id"]].append(li)  # unnamed gifts are each tested on their own
            if money(li["amount_usd"], li["line_id"]) >= NAME_FROM:
                unnamed.append(li["line_id"])
    totals = {k: sum((money(li["amount_usd"], li["line_id"]) for li in g), Decimal(0)) for k, g in groups.items()}
    over = {li["line_id"] for k, g in groups.items() if totals[k] > CAP for li in g}
    cited = tuple(li["line_id"] for li in lines if li["line_id"] in over or li["line_id"] in unnamed)
    shown = (f"per recipient {', '.join(f'${t}' for t in totals.values())} vs ${CAP} cap; "
             f"unnamed at ${NAME_FROM}+: {', '.join(unnamed) or 'none'}")
    if not cited:
        return Check("GIFT-01", "not_fired", detail=shown)
    return Check("GIFT-01", "fired", severity="medium", line_ids=cited, detail=shown)


def gift_checks(receipt: dict, categories: dict[str, str],
                is_gift_for: dict[str, tuple[str, str | None]] | None = None) -> list[Check]:
    """One Check for each of RULE_IDS (in that order). `categories` maps line_id -> category;
    `is_gift_for` maps line_id -> (recipient kind, name or None) for lines that name who they are for."""
    items = receipt["line_items"]
    cat = {li["line_id"]: categories[li["line_id"]] for li in items}  # a missing line raises KeyError
    hook = {} if is_gift_for is None else dict(is_gift_for)
    for lid, v in hook.items():
        if lid not in cat:
            raise ValueError(f"is_gift_for names {lid!r}, which is not on this receipt")
        if not (isinstance(v, tuple) and len(v) == 2 and v[0] in RECIPIENT_KINDS and (v[1] is None or isinstance(v[1], str))):
            raise ValueError(f"{lid}: is_gift_for must be (kind in {RECIPIENT_KINDS}, name or None), got {v!r}")
    for li in items:
        money(li["amount_usd"], li["line_id"])
    declared = receipt["submitted_expense_type"] == "Client Gifts"
    kind = {li["line_id"]: hook[li["line_id"]][0] if li["line_id"] in hook else "client" for li in items}
    names = {li["line_id"]: hook[li["line_id"]][1] if li["line_id"] in hook else None for li in items}

    def ids(lines):
        return tuple(li["line_id"] for li in lines)

    gifts = [li for li in items if cat[li["line_id"]] not in NOT_GIFTS and (declared or li["line_id"] in hook)]
    cards = [li for li in items if cat[li["line_id"]] == "gift_card"]  # never reimbursable, gift or not
    no_card = [li for li in gifts if cat[li["line_id"]] != "gift_card"]  # cards fall under GIFT-02 alone
    client = [li for li in no_card if kind[li["line_id"]] == "client"]
    staff = [li for li in no_card if kind[li["line_id"]] == "employee"]
    official = [li for li in items if kind[li["line_id"]] == "government_official" and cat[li["line_id"]] != "service_fee"]
    replaced = any(kind[li["line_id"]] == "government_official" for li in no_card)

    return [
        _gift01(client, names, replaced),
        Check("GIFT-02", "fired", severity="high", line_ids=ids(cards), detail="categorised gift_card, a cash equivalent")
        if cards else Check("GIFT-02", "not_applicable", detail="no gift_card line"),
        Check("GIFT-03", "fired", severity="medium", line_ids=ids(staff), detail="employee gift: goes through HR")
        if staff else Check("GIFT-03", "not_applicable", detail="no employee gift line"),
        Check("GIFT-04", "fired", severity="critical", line_ids=ids(official),
              detail="provided to a government official: route to Compliance")
        if official else Check("GIFT-04", "not_applicable",
                               detail="no line for a government official" + ("" if is_gift_for is not None else " (no recipient hook)")),
    ]
