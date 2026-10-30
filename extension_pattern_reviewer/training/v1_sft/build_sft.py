import json,sys,statistics
sys.path.insert(0,"/Users/geboou/Desktop/oversight/validator/src")
from validator.normaliser import normalise
SYSTEM=open("sft_data/SYSTEM_short.txt").read()
KEEP=("merchant_name","mcc","mcc_description","employee_country","entity","submitted_expense_type","currency","attendee_count","itemized")
def payload(r):
    lines=[{"line_id":l["line_id"],"description":normalise(l["description_raw"]),**{k:l[k] for k in ("language","quantity","amount","amount_usd")}} for l in r["line_items"]]
    return json.dumps({**{k:r[k] for k in KEEP},"line_items":lines},ensure_ascii=False,sort_keys=True)
def build(name):
    R=[json.loads(x) for x in open(f"data_synth/trainv1_clean_{name}_receipts.jsonl")]
    X={}
    for x in open(f"data_synth/trainv1_clean_{name}_expected.jsonl"):
        d=json.loads(x); X[d["line_id"]]=d
    out=[]
    for r in R:
        lines=[]
        for l in r["line_items"]:
            e=X[l["line_id"]]; gr=e.get("gift_recipient") or None
            lines.append({"line_id":l["line_id"],"description_en":e.get("description_en") or l["description_raw"],"category":e["category"],"other_kind":e["other_kind"],
                          "note":e.get("note") if e["category"]=="other" else None,"confidence":e["expected_confidence"],
                          "recipient_kind":(gr or {}).get("kind"),"recipient_name":None})
        out.append({"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":payload(r)},
                    {"role":"assistant","content":json.dumps({"lines":lines},ensure_ascii=False,separators=(",",":"))}]})
    return out
for n in ("train","valid"):
    rows=build(n)
    open(f"sft_data/{n}.jsonl","w").write("\n".join(json.dumps(r,ensure_ascii=False) for r in rows)+"\n")
    ch=[len("".join(m["content"] for m in r["messages"])) for r in rows]
    print(n,len(rows),"avg chars",int(statistics.mean(ch)),"max",max(ch))
