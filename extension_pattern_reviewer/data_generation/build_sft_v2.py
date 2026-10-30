import json, random, sys, collections
sys.path.insert(0,"/Users/geboou/Desktop/oversight/finetune/data_synth/pipeline"); sys.path.insert(0,"/Users/geboou/Desktop/oversight/finetune/v2")
import render_history as RH, gate
src=sys.argv[1] if len(sys.argv)>1 else None
# reuse SYSTEM and example() from v1 builder without executing its main body
code=open("/Users/geboou/Desktop/oversight/finetune/data_synth/pipeline/build_reviewer_sft.py").read()
i=code.index("SYSTEM = open"); j=code.index("fam = collections")
ns={"RH":RH,"json":json,"D":__import__("pathlib").Path("/Users/geboou/Desktop/oversight/finetune/data_synth")}
exec(code[i:j],ns); SYSTEM,chat=ns["SYSTEM"],ns["chat"]
fam={"claude_clF2":"claude_fraud2","claude_clC2":"claude_clean2","claude_clF":"claude_fraud","claude_clC":"claude_clean","deepseek_fraud_s1001":"deepseek_fraud","kimi_clean_s3001":"kimi_clean"}
H=[]
for f,n in fam.items():
    for h in json.load(open(f"out/{f}.json")): h["_fam"]=n; H.append(h)
rng=random.Random(2026)
def ex(h,hid):
    text,ids=RH.render(hid,h); pl=sorted(ids[r["receipt_id"]] for r in h["receipts"] if r.get("planted"))
    ans=json.dumps({"escalate":[{"receipt_id":r,"reason":h["reason"]} for r in pl]},ensure_ascii=False,separators=(",",":"))
    return text,ans
# gate
T=[];Y=[]
for k,h in enumerate(H):
    t,_=ex(h,f"V{k:03d}"); T.append(t); Y.append(1 if h["class"]=="fraud" else 0)
gate.report(T,Y,"v2 (n small)")
sch=sorted({h["scheme"] for h in H if h["class"]=="fraud"}); hold=set(rng.sample(sch,max(1,round(len(sch)*.2))))
cl=[h for h in H if h["class"]=="clean"]; rng.shuffle(cl); hc={h["history_id"] for h in cl[:round(len(cl)*.2)]}
val=[h for h in H if (h["class"]=="fraud" and h["scheme"] in hold) or h["history_id"] in hc]; tr=[h for h in H if h not in val]
rng.shuffle(tr)
for name,hs in(("train",tr),("valid",val)):
    rows=[]
    for k,h in enumerate(hs):
        t,a=ex(h,f"{name[0].upper()}{k+1:04d}"); rows.append(chat(t,a))
    open(f"sft/{name}.jsonl","w").write("\n".join(json.dumps(r,ensure_ascii=False) for r in rows)+"\n")
    print(name,len(hs),collections.Counter((h["_fam"]) for h in hs))
print("schemes",len(sch),"held",len(hold),sorted(hold)); json.dump({"heldout_schemes":sorted(hold),"heldout_clean":sorted(hc)},open("sft/split.json","w"),indent=1)
