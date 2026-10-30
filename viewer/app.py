"""Read-only viewer for the expense validator's committed outputs.

Launch:  uv run --group viewer streamlit run viewer/app.py
Deep link: ?receipt=RCP-016 opens that receipt's detail page.

Lives outside src/ on purpose: it reads the answer key (data_eval/gold.jsonl) for
display, so it must never be importable as a pipeline module. It reads JSON files
directly and makes no model calls.
"""

import html
import json
import re
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


CSS = """
<style>
.chip{display:inline-block;padding:.12rem .6rem;border-radius:999px;font-size:.82rem;font-weight:600;border:1px solid;white-space:nowrap;margin:0 .15rem}
.c-flag,.c-high{background:rgba(229,72,77,.16);color:#e5484d;border-color:rgba(229,72,77,.5)}
.c-review,.c-medium{background:rgba(245,166,35,.18);color:#d98a00;border-color:rgba(245,166,35,.55)}
.c-pass,.c-low,.c-ok{background:rgba(48,164,108,.16);color:#30a46c;border-color:rgba(48,164,108,.5)}
.c-neutral{background:rgba(128,128,128,.14);color:inherit;border-color:rgba(128,128,128,.4)}
.c-crit{background:#e5484d;color:#fff;border-color:#e5484d}
.cf-high{background:rgba(48,164,108,.16);color:#30a46c;border-color:rgba(48,164,108,.5)}
.cf-medium{background:rgba(245,166,35,.18);color:#d98a00;border-color:rgba(245,166,35,.55)}
.cf-low{background:rgba(229,72,77,.16);color:#e5484d;border-color:rgba(229,72,77,.5)}
.cf-rule{background:rgba(128,128,128,.14);color:inherit;border-color:rgba(128,128,128,.4)}
.c-good{background:#30a46c;color:#fff;border-color:#30a46c}
.hdr{display:flex;flex-wrap:wrap;align-items:center;gap:.4rem;margin:.2rem 0 .5rem}
.hdr .lbl{opacity:.65;font-size:.85rem;margin-left:.6rem}
.verdict{font-size:1.05rem;padding:.6rem .9rem;border-left:5px solid;border-radius:6px;background:rgba(128,128,128,.10);margin:.3rem 0 .8rem}
.verdict.good{border-color:#30a46c}.verdict.bad{border-color:#e5484d}.verdict.neutral{border-color:#888}
.facts{opacity:.8;font-size:.9rem;line-height:1.6}
.tblwrap{overflow-x:auto}
table.li{border-collapse:collapse;width:100%;font-size:.88rem}
table.li th{text-align:left;padding:.4rem .5rem;border-bottom:2px solid rgba(128,128,128,.4);white-space:nowrap}
table.li td{padding:.4rem .5rem;border-bottom:1px solid rgba(128,128,128,.2);vertical-align:top}
.bar{display:inline-block;width:70px;height:8px;border-radius:4px;background:rgba(128,128,128,.25);vertical-align:middle;margin-right:.4rem;overflow:hidden}
.bar>i{display:block;height:100%}
.bar.high>i{background:#30a46c}.bar.medium>i{background:#f5a623}.bar.low>i{background:#e5484d}.bar.rule>i{background:#888}
.note{opacity:.7;font-size:.8rem}
</style>
"""


def esc(x):
    return html.escape(str(x))


def chip(text, cls):
    return f'<span class="chip c-{cls}">{esc(text)}</span>'


def md(x):
    """Escape '$' so st.markdown/st.write never treat dollar amounts as math."""
    return str(x).replace("$", "\\$")


def money(x):
    try:
        return f"{float(x):,.2f}"
    except (TypeError, ValueError):
        return str(x)


def fmt(v):
    return "-" if v is None else ("yes" if v is True else "no" if v is False else v)


def disp_chip(d):
    return chip(d, d if d in CLASSES else "neutral")


def status_chip(s):
    return chip(s.upper() if s != "MISMATCH" else s, {"match": "good", "MISMATCH": "bad"}.get(s, "neutral"))


EMOJI = {"flag": "🔴", "review": "🟠", "pass": "🟢", "match": "✅", "MISMATCH": "❌", "stretch ✓": "✅", "stretch ✗": "❌"}


def status(rid, report, gold):
    if rid in OUT_OF_SCOPE:
        return "stretch ✓" if report[rid]["disposition"] == gold[rid]["labels"]["disposition"] else "stretch ✗"
    return "match" if report[rid]["disposition"] == gold[rid]["labels"]["disposition"] else "MISMATCH"


def _open(key):
    rid = st.session_state[key]
    st.session_state["page"] = "Receipt detail"
    st.session_state["rid"] = rid
    st.query_params["receipt"] = rid


def receipts_page(report, gold, facts):
    rows = [{"receipt": rid, "merchant": facts[rid]["merchant_name"], "MCC": facts[rid]["mcc"],
             "entity": facts[rid]["entity"], "system": report[rid]["disposition"],
             "correct": gold[rid]["labels"]["disposition"], "status": status(rid, report, gold),
             "exceptions": ", ".join(e["rule_id"] for e in report[rid]["exceptions"]) or "-",
             "review signals": ", ".join(s["rule_id"] for s in report[rid]["review_signals"]) or "-"}
            for rid in sorted(report)]
    df = pd.DataFrame(rows)
    scored = df[~df.receipt.isin(OUT_OF_SCOPE)]
    c1, c2, c3 = st.columns(3)
    c1.metric("Scored", len(scored))
    c2.metric("Out of scope", len(df) - len(scored))
    c3.metric("Mismatches", int((scored.status == "MISMATCH").sum()))
    q = st.text_input("Search by merchant or receipt id", placeholder="e.g. RCP-016 or Starbucks").strip().lower()
    f1, f2, f3 = st.columns([2, 1, 1])
    disp = f1.multiselect("System disposition", CLASSES, default=CLASSES)
    only_mis = f2.checkbox("Mismatches only")
    only_scored = f3.checkbox("Scored only")
    view = df[df.system.isin(disp)]
    if q:
        view = view[view.receipt.str.lower().str.contains(q, regex=False) | view.merchant.str.lower().str.contains(q, regex=False)]
    if only_mis:
        view = view[view.status == "MISMATCH"]
    if only_scored:
        view = view[~view.receipt.isin(OUT_OF_SCOPE)]
    st.caption(f"{len(view)} of {len(df)} receipts shown. Click a column header to sort. "
               "🔴 flag  🟠 review  🟢 pass  ·  ✅ match  ❌ MISMATCH  stretch = timing receipts (handled, not scored)")
    shown = view.copy()
    for col in ("system", "correct", "status"):
        shown[col] = shown[col].map(lambda v: f"{EMOJI[v]} {v}")
    if view.empty:
        st.success("No mismatches: all scored receipts match the answer key." if only_mis else "No receipts match these filters.")
    ev = st.dataframe(shown, hide_index=True, width="stretch", height=min(35 * (len(shown) + 1) + 3, 1200),
                      on_select="rerun", selection_mode="single-row", key="list",
                      column_config={"exceptions": st.column_config.TextColumn(width="large"),
                                     "review signals": st.column_config.TextColumn(width="medium")})
    opts = list(view.receipt)
    if not opts:
        return
    sel = ev.selection.rows[0] if ev.selection.rows else 0
    o1, o2 = st.columns([3, 1], vertical_alignment="bottom")
    o1.selectbox("Open receipt detail (click a row above to preselect)", opts, index=min(sel, len(opts) - 1),
                 key=f"open_{opts[min(sel, len(opts) - 1)]}")
    o2.button("Open", type="primary", on_click=_open, args=(f"open_{opts[min(sel, len(opts) - 1)]}",))


def exceptions_table(items, key="reason"):
    if not items:
        st.write("None.")
        return
    st.dataframe(pd.DataFrame([{"rule": e["rule_id"], "severity": e.get("severity", "-"), "policy": e.get("policy_doc", "-"),
                                "lines": ", ".join(e.get("line_ids", [])), key: e.get(key, "")} for e in items]),
                 hide_index=True, width="stretch",
                 column_config={"rule": st.column_config.TextColumn(width="small"), "severity": st.column_config.TextColumn(width="small"),
                                "policy": st.column_config.TextColumn(width="medium"), "lines": st.column_config.TextColumn(width="medium"),
                                key: st.column_config.TextColumn(width="large")})


def line_items_html(lines, cited, gold_lines):
    out = ['<div class="tblwrap"><table class="li"><tr><th>Line</th><th>Description</th><th>USD</th><th>Category (system)</th>'
           '<th>Correct category</th><th>Confidence</th><th>Cited by</th></tr>']
    for li in lines:
        band = li["confidence_band"] if li["confidence_band"] in ("high", "medium", "low") else "rule"
        gold_cat = gold_lines.get(li["line_id"], {}).get("category")
        if gold_cat is None:
            correct = "-"
        else:
            same = gold_cat == li["category"]
            correct = chip(gold_cat, "neutral") + chip("✓" if same else "✗ differs", "good" if same else "bad")
        pct = max(0, min(100, round(float(li["confidence"]) * 100)))
        en = li.get("description_en", "")
        desc = esc(li["description_raw"]) + (f'<div class="note">{esc(en)}</div>' if en and en != li["description_raw"] else "")
        if li.get("category_note"):
            desc += f'<div class="note">Note: {esc(li["category_note"])}</div>'
        cat = chip(li["category"], "neutral") + (chip("restricted", "flag") if li["restricted"] else "")
        rules = " ".join(chip(r, "review") for r in cited.get(li["line_id"], [])) or "-"
        out.append(f'<tr><td>{esc(li["line_id"])}</td><td>{desc}</td><td>{esc(money(li["amount_usd"]))}</td><td>{cat}</td><td>{correct}</td>'
                   f'<td><span class="bar {band}"><i style="width:{pct}%"></i></span>{li["confidence"]} '
                   f'<span class="chip cf-{band}">{esc(band)}{" (set by rule)" if band == "rule" else ""}</span></td>'
                   f'<td>{rules}</td></tr>')
    out.append("</table></div>")
    return "".join(out)


def detail_page(report, gold, facts, rid):
    r, g, f = report[rid], gold[rid], facts[rid]
    lab = g["labels"]
    stt = status(rid, report, gold)

    # diff computed first so the summary can sit at the top
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

    st.subheader(md(f"{rid}: {f['merchant_name']}"))
    st.markdown(f'<div class="hdr"><span class="lbl">System</span>{disp_chip(r["disposition"])}'
                f'<span class="lbl">Correct</span>{disp_chip(lab["disposition"])}'
                f'<span class="lbl"></span>{status_chip(stt)}</div>', unsafe_allow_html=True)
    n_ex = len(r["exceptions"])
    tail = "all matched" if not diffs else f"{len(diffs)} difference{'s' if len(diffs) != 1 else ''} from the answer key"
    if not r["exceptions"] and r["review_signals"]:
        tail += ", review because of " + ", ".join(s["rule_id"] for s in r["review_signals"])
    if rid in OUT_OF_SCOPE:
        tail += " (stretch: timing rule handled, not scored)"
    vcls = "neutral" if rid in OUT_OF_SCOPE else ("good" if not diffs and stt == "match" else "bad")
    st.markdown(f'<div class="verdict {vcls}">System: <b>{esc(r["disposition"])}</b>, correct: <b>{esc(lab["disposition"])}</b>, '
                f'{n_ex} exception{"s" if n_ex != 1 else ""}, {tail}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="facts">MCC {esc(f["mcc"])} ({esc(f["mcc_description"])}) · {esc(f["entity"])} / {esc(f["employee_country"])} · '
                f'{esc(f["submitted_expense_type"])} · {esc(str(f["transaction_datetime"]).replace("T", " ")[:16])} · <b>{esc(money(f["total_amount"]))} {esc(f["currency"])}</b> '
                f'(&#36;{esc(money(f["total_amount_usd"]))}) · attendees {esc(fmt(f["attendee_count"]))} · trip nights {esc(fmt(f["trip_nights"]))} · '
                f'pre-approval {esc(fmt(f["pre_approval_ref"]))} · itemized {esc(fmt(f["itemized"]))}</div>', unsafe_allow_html=True)

    cited = {}
    for e in r["exceptions"]:
        for lid in e["line_ids"]:
            cited.setdefault(lid, []).append(e["rule_id"])
    if r["review_signals"]:
        st.markdown(f"#### {'Review signals' if r['exceptions'] else 'Why review: review signals'} ({len(r['review_signals'])})")
        st.caption("A review signal sends the receipt to a human without raising an exception.")
        for s_ in r["review_signals"]:
            with st.container(border=True):
                st.markdown(f"**{s_['rule_id']}** {chip('review signal', 'review')} {chip(s_.get('policy_doc', '-'), 'neutral')}",
                            unsafe_allow_html=True)
                st.write("Why: " + md(s_.get("reason", "")))
    st.markdown("#### Line items (system)")
    st.markdown(line_items_html(r["line_items"], cited, g["line_labels"]), unsafe_allow_html=True)

    st.markdown(f"#### Exceptions raised ({len(r['exceptions'])})")
    if not r["exceptions"]:
        st.write("None raised" + (": the receipt goes to review because of the review signals above." if r["review_signals"] else "."))
    for e in r["exceptions"]:
        sev = str(e["severity"]).lower()
        with st.container(border=True):
            st.markdown(f"**{e['rule_id']}** {chip('severity: ' + str(e['severity']), {'critical': 'crit', 'high': 'high', 'medium': 'medium', 'low': 'low'}.get(sev, 'neutral'))} "
                        f"{chip(e['policy_doc'], 'neutral')}", unsafe_allow_html=True)
            st.markdown("Policy text (verbatim):")
            st.markdown("\n".join("> " + ln.replace("$", "\\$") for ln in e["evidence"].splitlines()))
            st.write("Why: " + e['explanation'].replace("$", "\\$"))
            for li in e.get("lines", []):
                st.markdown(f"- Cited line **{li['line_id']}**: {md(li['description_raw'])} (\\${money(li['amount_usd'])})")

    st.divider()
    st.header("Correct answer (answer key)")
    if rid in OUT_OF_SCOPE:
        st.warning("Out of scope: not scored.")
    st.markdown("#### Diff: system vs correct")
    if diffs:
        st.warning(f"{len(diffs)} difference{'s' if len(diffs) != 1 else ''} between system and answer key")
        st.markdown("\n".join("- " + md(d) for d in diffs))
    else:
        st.success("No differences: system matches the answer key.")

    left, right = st.container(), st.container()
    with left:
        st.markdown("##### System")
        st.markdown(f"**System disposition:** {disp_chip(r['disposition'])}", unsafe_allow_html=True)
        st.markdown("Exceptions")
        exceptions_table(r["exceptions"], key="explanation")
        st.markdown("Review signals")
        exceptions_table(r["review_signals"])
    with right:
        st.markdown("##### Answer key")
        st.markdown(f"**Expected disposition:** `{lab['disposition']}`")
        st.markdown("Expected exceptions")
        exceptions_table(lab["expected_exceptions"])
        st.markdown("Expected review signals")
        exceptions_table(lab["review_signals"])
        st.write(f"**Notes:** {md(g['notes'])}")

    t1, t2, t3 = st.tabs([f"Superseded rules ({len(r['superseded'])})",
                          f"Rules considered ({len(r['rules_considered'])})", "Line labels (answer key)"])
    with t1:
        exceptions_table(r["superseded"])
    with t2:
        exceptions_table(r["rules_considered"], key="why")
    with t3:
        st.dataframe(pd.DataFrame([{"line": k, **v} for k, v in g["line_labels"].items()]), hide_index=True, width="stretch")


def parse_eval(md):
    """Split EVAL.md into (preamble, [(title, body)]) and parse the Headline table; defensive: any failure yields no table."""
    parts = re.split(r"^## (.+)$", md, flags=re.M)
    sections = list(zip(parts[1::2], parts[2::2]))
    table = {}
    try:
        body = dict(sections).get("Headline", "")
        rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in body.splitlines() if ln.strip().startswith("|")]
        rows = [r for r in rows if len(r) >= 4 and not set("".join(r)) <= set("-: ")]
        table = {r[0]: r[1:4] for r in rows[1:]}
    except Exception:
        table = {}
    return parts[0], sections, table


def metrics_page(report, gold):
    scored = [rid for rid in sorted(report) if rid not in OUT_OF_SCOPE]
    cells = [{"correct": c, "system": s, "n": sum(gold[r]["labels"]["disposition"] == c and report[r]["disposition"] == s for r in scored)}
             for c in CLASSES for s in CLASSES]
    try:
        md_text = (ROOT / "output" / "EVAL.md").read_text(encoding="utf-8")
    except OSError:
        md_text = ""
    pre, sections, table = parse_eval(md_text)

    def find(prefix):
        return next((v for k, v in table.items() if k.lower().startswith(prefix.lower())), None)

    kpis = [("Disposition accuracy", "Disposition accuracy", "Higher is better."),
            ("False positives", "False positives", "Of 9 pass receipts, wrongly sent to flag/review. Lower is better."),
            ("Missed violations", "Missed violations", "Of 16 flag receipts, passed or downgraded. Lower is better."),
            ("Macro F1", "Macro F1", "Mean over categories. Higher is better."),
            ("F1, restricted", "F1, restricted", "restricted = true. Higher is better."),
            ("Exception precision", "Exception precision", "By rule id. Higher is better."),
            ("Exception recall", "Exception recall", "By rule id. Higher is better.")]
    st.markdown("#### Headline (system A, from output/EVAL.md)")
    if any(find(p) for _, p, _ in kpis):
        for chunk in (kpis[:4], kpis[4:]):
            for col, (label, prefix, hint) in zip(st.columns(4), chunk):
                row = find(prefix)
                if not row:
                    col.metric(label, "n/a")
                    continue
                a = row[0]
                rest = a.split("=")[-1].strip()
                col.metric(label, re.split(r"\s*(?:\[|boot\[|W\[)", rest)[0].strip() or a, help=hint)
                ci = re.search(r"\[([^\]]+)\]", rest)
                frac = a.split("=")[0].strip() if "=" in a else ""
                col.caption(f"{frac}  95% CI [{ci.group(1)}]" if ci else frac)
    else:
        st.warning("Could not parse the Headline table in output/EVAL.md; showing the raw markdown instead.")
        st.markdown(md_text or "output/EVAL.md not found.")

    if table:
        pick = ["Disposition accuracy", "False positives", "Missed violations", "Exception precision", "Exception recall",
                "Line category accuracy", "Restricted-flag accuracy", "Macro F1", "F1, restricted"]
        comp = [{"measure": k, "A LLM": v[0].split(" [")[0].split(" boot[")[0], "B ORACLE": v[1].split(" [")[0].split(" boot[")[0],
                 "C KEYWORD": v[2].split(" [")[0].split(" boot[")[0]}
                for p in pick for k, v in table.items() if k.lower().startswith(p.lower())][:len(pick)]
    else:
        comp = []

    st.markdown(f"#### Confusion matrix, committed output vs answer key ({len(scored)} scored receipts)")
    st.caption("Rows = correct answer, columns = system. Diagonal = agreement.")
    cm = pd.DataFrame(cells).pivot(index="correct", columns="system", values="n").loc[CLASSES, CLASSES]
    st.dataframe(cm, width="stretch")  # small 3x3, never truncated
    enc = {"x": {"field": "system", "type": "nominal", "sort": CLASSES}, "y": {"field": "correct", "type": "nominal", "sort": CLASSES}}
    st.vega_lite_chart(pd.DataFrame(cells), {"layer": [
        {"mark": "rect", "encoding": {**enc, "color": {"field": "n", "type": "quantitative", "scale": {"scheme": "blues"}}}},
        {"mark": {"type": "text", "fontSize": 16}, "encoding": {**enc, "text": {"field": "n"},
         "color": {"condition": {"test": "datum.n > 6", "value": "white"}, "value": "black"}}}]}, width="stretch")

    if comp:
        st.markdown("#### System A vs oracle B vs keyword C")
        st.table(pd.DataFrame(comp).set_index("measure"))
        st.caption("Point estimates only; confidence intervals are in the full Headline table below.")

    st.markdown("#### output/EVAL.md")
    if pre.strip():
        with st.expander("Title and preamble"):
            st.markdown(pre)
    for title, body in sections:
        with st.expander(title, expanded=(title == "Headline")):
            st.markdown(body)
    if not sections and md_text and table:
        st.markdown(md_text)


def main():
    st.set_page_config(page_title="Expense validator viewer", page_icon="🧾", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    report, gold, facts = load()
    st.info("The answer key is shown for evaluation only; the pipeline never reads it.")
    qp_rid = st.query_params.get("receipt")
    ids = sorted(report)
    if "page" not in st.session_state:
        st.session_state["page"] = "Receipt detail" if qp_rid in report else "Receipts"
    if "rid" not in st.session_state or st.session_state["rid"] not in ids:
        st.session_state["rid"] = qp_rid if qp_rid in report else ids[0]
    page = st.sidebar.radio("Page", PAGES, key="page")
    if page == "Receipt detail":
        rid = st.sidebar.selectbox("Receipt", ids, key="rid",
                                   format_func=lambda i: f"{EMOJI[status(i, report, gold)]} {i} · {status(i, report, gold)}")
        st.query_params["receipt"] = rid
        detail_page(report, gold, facts, rid)
    elif page == "Metrics":
        st.query_params.clear()
        metrics_page(report, gold)
    else:
        st.query_params.clear()
        receipts_page(report, gold, facts)


main()
