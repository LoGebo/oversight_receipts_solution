"""Helpers shared by the test modules (imported as `from conftest import ...`)."""
import json

import pytest
from anthropic.types import Message

from validator import classifier
from validator.check import Check
from validator.engine import Result
from validator.loader import load_receipts

@pytest.fixture(autouse=True)
def sleeps(monkeypatch):
    """The classifier's retry waits, recorded instead of slept."""
    waits = []
    monkeypatch.setattr(classifier, "sleep", waits.append)
    return waits


RECEIPTS = {r["receipt_id"]: r for r in load_receipts()}
MEAL = ("food_beverage", "food_beverage", "food_beverage", "service_fee")
CASES = {  # hand-written categories, one real receipt per disposition (and one APAC override)
    "RCP-001": (MEAL, "pass"),
    "RCP-026": (("computer_accessory", "computer_accessory"), "flag"),
    "RCP-028": (("health_otc", "health_otc"), "review"),
    "RCP-016": (("food_beverage", "alcohol", "service_fee"), "flag"),
}


def fired(checks):
    return {c.rule_id: (c.severity, c.line_ids) for c in checks if c.status == "fired"}


def status(checks):
    return {c.rule_id: c.status for c in checks}


def cats(rid, *categories):
    """Categories given in line order: RCP-001-L1, RCP-001-L2, ..."""
    return {f"{rid}-L{i}": c for i, c in enumerate(categories, 1)}


def suffix_cats(receipt, by_suffix):
    """{line suffix such as "L2": category}; every other line of the receipt is `other`."""
    return {li["line_id"]: by_suffix.get(li["line_id"].rsplit("-", 1)[1], "other") for li in receipt["line_items"]}


class Fake:
    """Stands in for anthropic.Anthropic: replies in order with real Message objects; an Exception reply is raised."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        text, stop = reply if isinstance(reply, tuple) else (reply, "end_turn")
        return Message.model_validate({
            "id": "msg_fake", "type": "message", "role": "assistant", "model": kw["model"], "stop_sequence": None,
            "stop_reason": stop, "content": [{"type": "text", "text": text}] if text else [],
            "usage": {"input_tokens": 1000, "output_tokens": 200}})


def line(lid, cat="food_beverage", conf="high", kind=None, name=None, other_kind="none", note=None, en=None):
    return {"line_id": lid, "description_en": en or f"text of {lid}", "category": cat, "other_kind": other_kind,
            "note": note, "confidence": conf, "recipient_kind": kind, "recipient_name": name}


def reply(*lines):
    return json.dumps({"lines": list(lines)})


def synthetic():
    """(results, gold, categories) for three scored receipts plus one out of scope, every count known by hand.

    T-1 pass, got review via EXC-03. T-2 flag: ALC-01 matched with one line too many, TECH-01 and REG-05 extra.
    T-3 flag: GIFT-04 missed, MCC-02 matched, got review. RCP-020 is out of scope and wrong on purpose.
    """
    def g(disp, exc=(), sig=(), lines=None):
        return {"labels": {"disposition": disp, "review_signals": [{"rule_id": s} for s in sig],
                           "expected_exceptions": [{"rule_id": r, "line_ids": list(ls)} for r, ls in exc]},
                "line_labels": {k: {"category": c, "restricted": rs} for k, (c, rs) in (lines or {}).items()}}

    gold = {"T-1": g("pass", lines={"T-1-L1": ("food_beverage", False)}),
            "T-2": g("flag", [("ALC-01", ["T-2-L1"])], lines={"T-2-L1": ("alcohol", True), "T-2-L2": ("food_beverage", False)}),
            "T-3": g("flag", [("GIFT-04", ["T-3-L1"])], ["MCC-02"], lines={"T-3-L1": ("gift", True)}),
            "RCP-020": g("flag", [("TIME-03", [])])}
    results = {
        "T-1": Result("T-1", "review", (Check("EXC-03", "fired", "signal", line_ids=("T-1-L1",)),)),
        "T-2": Result("T-2", "flag", (Check("ALC-01", "fired", severity="high", line_ids=("T-2-L1", "T-2-L2")),
                                      Check("TECH-01", "fired", severity="high", line_ids=("T-2-L2",)),
                                      Check("REG-05", "fired", "signal"))),
        "T-3": Result("T-3", "review", (Check("MCC-02", "fired", "signal"), Check("GIFT-04", "not_fired")), error="gifts: boom"),
        "RCP-020": Result("RCP-020", "pass"),
    }
    categories = {"T-1-L1": "food_beverage", "T-2-L1": "alcohol", "T-2-L2": "alcohol", "T-3-L1": "mobile_handset"}
    return results, gold, categories
