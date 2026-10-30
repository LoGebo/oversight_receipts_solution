"""Read-only viewer for the expense validator's committed outputs.

Launch:  uv run --group viewer streamlit run viewer/app.py
Deep link: ?receipt=RCP-016 opens that receipt's detail page.

Lives outside src/ on purpose: it reads the answer key (data_eval/gold.jsonl) for
display, so it must never be importable as a pipeline module. It reads JSON files
directly and makes no model calls.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
# Mirrors validator.gold.OUT_OF_SCOPE (tests check they agree); kept here so the viewer imports nothing from the evaluator.
OUT_OF_SCOPE = {"RCP-020", "RCP-021", "RCP-029", "RCP-030"}
CLASSES = ["flag", "review", "pass"]
PAGES = ["Receipts", "Receipt detail", "Metrics"]


def _jsonl(rel):
    with open(ROOT / rel, encoding="utf-8") as f:
        return {r["receipt_id"]: r for r in map(json.loads, f) if r}


@st.cache_data
def load():
    return _jsonl("output/report.jsonl"), _jsonl("data_eval/gold.jsonl"), _jsonl("data_split/receipts_input.jsonl")


def status(rid, report, gold):
    if rid in OUT_OF_SCOPE:
        return "out of scope"
    return "match" if report[rid]["disposition"] == gold[rid]["labels"]["disposition"] else "MISMATCH"


def receipts_page(report, gold, facts):
    rows = [{"receipt": rid, "merchant": facts[rid]["merchant_name"], "MCC": facts[rid]["mcc"],
             "entity": facts[rid]["entity"], "system": report[rid]["disposition"],
             "correct": gold[rid]["labels"]["disposition"], "status": status(rid, report, gold)}
            for rid in sorted(report)]
    df = pd.DataFrame(rows)
    scored = df[df.status != "out of scope"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Scored", len(scored))
    c2.metric("Out of scope", len(df) - len(scored))
    c3.metric("Mismatches", int((scored.status == "MISMATCH").sum()))
    disp = st.multiselect("System disposition", CLASSES, default=CLASSES)
    only_mis = st.checkbox("Mismatches only")
    only_scored = st.checkbox("Scored only")
    view = df[df.system.isin(disp)]
    if only_mis:
        view = view[view.status == "MISMATCH"]
    if only_scored:
        view = view[view.status != "out of scope"]
    st.caption(f"{len(view)} of {len(df)} receipts shown. Click a column header to sort.")
    st.dataframe(view, hide_index=True, width="stretch")


def exceptions_table(items, key="reason"):
    if not items:
        st.write("None.")
        return
    st.dataframe(pd.DataFrame([{"rule": e["rule_id"], "severity": e.get("severity", "-"), "policy": e.get("policy_doc", "-"),
                                "lines": ", ".join(e.get("line_ids", [])), key: e.get(key, "")} for e in items]),
                 hide_index=True, width="stretch")


def detail_page(report, gold, facts, rid):
    r, g, f = report[rid], gold[rid], facts[rid]
    st.subheader(f"{rid}: {f['merchant_name']}")
    st.write(f"**Status:** {status(rid, report, gold)} · **System:** `{r['disposition']}` · **Correct:** `{g['labels']['disposition']}`")
    st.write(f"MCC {f['mcc']} ({f['mcc_description']}) · {f['entity']} / {f['employee_country']} · "
             f"{f['submitted_expense_type']} · {f['transaction_datetime']} · {f['total_amount']} {f['currency']} "
             f"(${f['total_amount_usd']}) · attendees {f['attendee_count']} · trip nights {f['trip_nights']} · "
             f"pre-approval {f['pre_approval_ref']} · itemized {f['itemized']}")

    cited = {}
    for e in r["exceptions"]:
        for lid in e["line_ids"]:
            cited.setdefault(lid, []).append(e["rule_id"])
    st.markdown("#### Line items (system)")
    st.dataframe(pd.DataFrame([{"line": li["line_id"], "raw": li["description_raw"], "English": li.get("description_en", ""),
                                "USD": li["amount_usd"], "category": li["category"], "restricted": li["restricted"],
                                "confidence": li["confidence"], "band": li["confidence_band"],
                                "note": li.get("category_note", ""), "cited by": ", ".join(cited.get(li["line_id"], []))}
                               for li in r["line_items"]]), hide_index=True, width="stretch")

    st.markdown(f"#### Exceptions raised ({len(r['exceptions'])})")
    if not r["exceptions"]:
        st.write("None.")
    for e in r["exceptions"]:
        with st.container(border=True):
            st.markdown(f"**{e['rule_id']}** · severity **{e['severity']}** · `{e['policy_doc']}`")
            st.markdown("Policy text (verbatim):")
            st.markdown("\n".join("> " + ln for ln in e["evidence"].splitlines()))
            st.write(f"Why: {e['explanation']}")
            for li in e.get("lines", []):
                st.markdown(f"- Cited line **{li['line_id']}**: {li['description_raw']} (${li['amount_usd']})")
    st.markdown("#### Review signals")
    exceptions_table(r["review_signals"])
    st.markdown("#### Superseded rules")
    exceptions_table(r["superseded"])
    with st.expander(f"Rules considered by the retriever ({len(r['rules_considered'])})"):
        exceptions_table(r["rules_considered"], key="why")

    st.divider()
    st.header("Correct answer (answer key)")
    st.info("The answer key is shown for evaluation only; the pipeline never reads it.")
    if rid in OUT_OF_SCOPE:
        st.warning("Out of scope: not scored.")
    lab = g["labels"]
    st.write(f"**Expected disposition:** `{lab['disposition']}`")
    st.markdown("Expected exceptions")
    exceptions_table(lab["expected_exceptions"])
    st.markdown("Expected review signals")
    exceptions_table(lab["review_signals"])
    st.write(f"**Notes:** {g['notes']}")

    st.markdown("#### Diff: system vs correct")
    got = {e["rule_id"]: set(e["line_ids"]) for e in r["exceptions"]}
    want = {e["rule_id"]: set(e["line_ids"]) for e in lab["expected_exceptions"]}
    sig_got, sig_want = {s["rule_id"] for s in r["review_signals"]}, {s["rule_id"] for s in lab["review_signals"]}
    sys_lines = {li["line_id"]: li for li in r["line_items"]}
    diffs = [f"Missing exception **{k}**" for k in sorted(want.keys() - got.keys())]
    diffs += [f"Extra exception **{k}**" for k in sorted(got.keys() - want.keys())]
    diffs += [f"**{k}** cites lines {sorted(got[k])}, expected {sorted(want[k])}" for k in sorted(got.keys() & want.keys()) if got[k] != want[k]]
    diffs += [f"Missing signal **{k}**" for k in sorted(sig_want - sig_got)] + [f"Extra signal **{k}**" for k in sorted(sig_got - sig_want)]
    diffs += [f"Line **{lid}**: system `{sys_lines[lid]['category']}`, correct `{ll['category']}`"
              for lid, ll in g["line_labels"].items() if lid in sys_lines and sys_lines[lid]["category"] != ll["category"]]
    st.markdown("\n".join("- " + d for d in diffs) if diffs else "No differences: system matches the answer key.")
    st.markdown("Line labels (answer key)")
    st.dataframe(pd.DataFrame([{"line": k, **v} for k, v in g["line_labels"].items()]), hide_index=True, width="stretch")


def metrics_page(report, gold):
    scored = [rid for rid in sorted(report) if rid not in OUT_OF_SCOPE]
    cells = [{"correct": c, "system": s, "n": sum(gold[r]["labels"]["disposition"] == c and report[r]["disposition"] == s for r in scored)}
             for c in CLASSES for s in CLASSES]
    st.markdown(f"#### Confusion matrix, committed output vs answer key ({len(scored)} scored receipts)")
    st.dataframe(pd.DataFrame(cells).pivot(index="correct", columns="system", values="n").loc[CLASSES, CLASSES], width="stretch")
    enc = {"x": {"field": "system", "type": "nominal", "sort": CLASSES}, "y": {"field": "correct", "type": "nominal", "sort": CLASSES}}
    st.vega_lite_chart(pd.DataFrame(cells), {"layer": [
        {"mark": "rect", "encoding": {**enc, "color": {"field": "n", "type": "quantitative", "scale": {"scheme": "blues"}}}},
        {"mark": {"type": "text", "fontSize": 16}, "encoding": {**enc, "text": {"field": "n"}}}]}, width="stretch")
    st.markdown("#### output/EVAL.md")
    st.markdown((ROOT / "output" / "EVAL.md").read_text(encoding="utf-8"))


def main():
    st.set_page_config(page_title="Expense validator viewer", layout="wide")
    report, gold, facts = load()
    st.info("The answer key is shown for evaluation only; the pipeline never reads it.")
    qp_rid = st.query_params.get("receipt")
    page = st.sidebar.radio("Page", PAGES, index=1 if qp_rid in report else 0)
    if page == "Receipt detail":
        ids = sorted(report)
        rid = st.sidebar.selectbox("Receipt", ids, index=ids.index(qp_rid) if qp_rid in report else 0,
                                   format_func=lambda i: f"{i} · {status(i, report, gold)}")
        st.query_params["receipt"] = rid
        detail_page(report, gold, facts, rid)
    elif page == "Metrics":
        st.query_params.clear()
        metrics_page(report, gold)
    else:
        st.query_params.clear()
        receipts_page(report, gold, facts)


main()
