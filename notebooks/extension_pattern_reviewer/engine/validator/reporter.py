"""Exception reporter (component 5): engine Result -> the per-receipt JSON object of the brief.

Deterministic, no LLM. Every fired exception names its rule, severity, the policy document it comes
from and that rule's text, quoted verbatim from data/policy-docs/*.md (parsed at runtime: the
document of a rule is the file its `**RULE-ID — title.**` paragraph is in) as plain text: markdown
emphasis and code marks removed, line breaks collapsed (plain()). The explanation is one sentence built
from the rule's title, the cited lines (or the receipt) with their amounts, and the engine's `detail`. Fired signals (MCC-02, EXC-03, ...) become review signals; superseded rules are
listed apart as context. An ERR-<family> signal (that rule family raised for this receipt) is a
review signal carrying the error, with no policy document. not_fired / not_applicable / superseded are never exceptions.
Line items carry the taxonomy category (an engine refinement such as mobile_handset is reported as
`other` with `category_detail`), the restricted flag of that taxonomy category, `category_note` on
every `other` line, and `description_en` when the classifier returned one. `rules_considered` lists
the retriever's candidate rules with their policy documents.
EXC-04 is re-checked here, fail loud: cited lines are on the receipt, never a service_fee line,
and each rule appears at most once.
"""
import re
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from validator.engine import Result
from validator.rules.documentation import EXTENSIONS

if TYPE_CHECKING:
    from validator.classifier import Classification

POLICY_DIR = Path(__file__).resolve().parents[2] / "data" / "policy-docs"
# `**ID — title.** body` up to the first blank line. Limit: first paragraph only; MEAL-01's
# definition list after it is not quoted (the cap and severity are in the first paragraph).
_RULE = re.compile(r"^\*\*([A-Z]+-\d+) — (.+?)\*\* *(.+?)(?=\n\n|\Z)", re.M | re.S)
CONFIDENCE = {"rule": 1.0, "high": 0.9, "medium": 0.7, "low": 0.3}
"""Band -> the number in [0, 1] the brief asks for. A reporting convention: the numbers are ordinal, not
calibrated probabilities. EXC-03 treats confidence < 0.5 (the low band, 0.3) as uncertain. "rule" is a
category set by rule, not by the model (a non-itemized charge is `other`)."""


@lru_cache(maxsize=1)
def _rules() -> dict[str, tuple[str, str, str]]:
    out = {}
    for path in sorted(POLICY_DIR.glob("*.md")):
        for rid, title, body in _RULE.findall(path.read_text(encoding="utf-8")):
            if rid in out:
                raise ValueError(f"{rid} is defined in both {out[rid][0]} and {path.name}")
            out[rid] = (path.name, title, body.strip())
    return out


def plain(text: str) -> str:
    """Markdown policy text as plain text: `**`, `*` and backticks dropped, whitespace collapsed."""
    return " ".join(re.sub(r"\*+|`", "", text).split())


def _usd(value) -> str:
    return f"${value:,.2f}" if type(value) in (int, float) else repr(value)


def explanation(check, receipt: dict) -> str:
    """One plain sentence: rule and title, severity, what it is raised on (items and amounts), and why."""
    by_id = {li["line_id"]: li for li in receipt["line_items"]}
    items = [f"'{' '.join(by_id[i]['description_raw'].split())}' ({_usd(by_id[i]['amount_usd'])})" for i in check.line_ids]
    if items:
        on = items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
    else:
        total = receipt.get("total_amount_usd")
        on = (f"the receipt from {receipt.get('merchant_name') or 'an unnamed merchant'}"
              + (f" ({_usd(total)} total)" if type(total) in (int, float) else ""))
    title = _rules()[check.rule_id][1].rstrip(".")
    return f"{check.rule_id} ({title}) raises a {check.severity} exception on {on}: {check.detail.rstrip('.')}."


def policy_text(rule_id: str) -> tuple[str, str]:
    """(policy document file name, the rule's text verbatim). KeyError if no paragraph defines it."""
    doc, _, text = _rules()[rule_id]
    return doc, text


def report(receipt: dict, result: Result, classification: "Classification | None" = None) -> dict:
    rid = receipt["receipt_id"]
    if result.receipt_id != rid:
        raise ValueError(f"result {result.receipt_id} is not for receipt {rid}")
    lines = {li["line_id"]: li for li in receipt["line_items"]}
    cats = classification.categories if classification else {}
    meta = classification.meta if classification else {}

    items = []
    for lid, li in lines.items():
        row = {"line_id": lid, "description_raw": li["description_raw"], "amount_usd": li["amount_usd"]}
        if lid in cats:
            band = meta.get("confidence", {}).get(lid)
            category = EXTENSIONS.get(cats[lid], cats[lid])
            row.update(category=category, restricted=classification.restricted[lid],
                       confidence=CONFIDENCE.get(band, 0.0), confidence_band=band or "failed")
            if cats[lid] in EXTENSIONS:
                row["category_detail"] = cats[lid]
            if category == "other":
                row["category_note"] = classification.notes.get(lid, "no note given")
            if lid in classification.english:
                row["description_en"] = classification.english[lid]
        items.append(row)

    ids = [c.rule_id for c in result.checks]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{rid}: a rule appears more than once")
    exceptions, signals, superseded = [], [], []
    for c in result.checks:
        if c.status == "superseded":
            superseded.append({"rule_id": c.rule_id, "reason": c.detail})
        if c.status != "fired":
            continue
        if c.rule_id.startswith("ERR-"):
            signals.append({"rule_id": c.rule_id, "policy_doc": None, "reason": c.detail, "line_ids": []})
            continue
        doc, text = policy_text(c.rule_id)
        if c.kind == "signal":
            signals.append({"rule_id": c.rule_id, "policy_doc": doc, "reason": c.detail,
                            "line_ids": list(c.line_ids)})
            continue
        for lid in c.line_ids:
            if lid not in lines:
                raise ValueError(f"{rid} {c.rule_id}: cites {lid}, which is not on the receipt")
            if cats.get(lid) == "service_fee":
                raise ValueError(f"{rid} {c.rule_id}: cites service fee / gratuity line {lid} (EXC-04)")
        exceptions.append({
            "rule_id": c.rule_id, "policy_doc": doc, "severity": c.severity, "line_ids": list(c.line_ids),
            "evidence": plain(text), "explanation": explanation(c, receipt),
            "lines": [{k: lines[lid][k] for k in ("line_id", "description_raw", "amount_usd")} for lid in c.line_ids],
        })

    out = {"receipt_id": rid, "disposition": result.disposition, "line_items": items,
           "exceptions": exceptions, "review_signals": signals, "superseded": superseded,
           "rules_considered": [{"rule_id": r, "policy_doc": policy_text(r)[0], "why": why}
                                for r, why in result.considered.items()]}
    if result.error:
        out.update(disposition="review" if result.disposition == "pass" else result.disposition, error=result.error)
    if meta.get("model"):
        out["model"] = meta["model"]
    return out
