"""Bundle everything the final notebook needs to recompute the metrics into one JSON (no dependency on 400 files)."""
import json, glob, re
D = "/Users/geboou/Desktop/oversight/finetune/data_synth/"; R = "/Users/geboou/Desktop/oversight/finetune/results/"
def amounts(inp):
    a = {}
    for h in inp:
        for m in re.finditer(r"^- (\S+-R\d+) \|[^|]*\|[^|]*\|[^|]*\| \$([\d,]+\.\d\d)", h["text"], re.M): a[m.group(1)] = float(m.group(2).replace(",", ""))
    return a
def files(model, pat):
    p = {}
    for f in glob.glob(D + f"review_out/{model}_{pat}*.json"):
        for h in json.load(open(f)): p[h["history_id"]] = [e["receipt_id"] for e in h.get("escalate", [])]
    return p
def tuned(path): return {h: v["escalate"] for h, v in json.load(open(path)).items()}
def api(tag):
    d = json.load(open(R + f"api_{tag}.json")); return {h: v["escalate"] for h, v in d.items()}, {"in": sum((v.get("usage") or {}).get("input_tokens", 0) for v in d.values()), "out": sum((v.get("usage") or {}).get("output_tokens", 0) for v in d.values()), "n": len(d)}
k14 = json.load(open(D + "reviewer_sft/eval_key.json")); i14 = json.load(open(D + "reviewer_sft/eval_inputs.json"))
k5 = json.load(open(D + "reviewer_sft/eval5_key.json")); i5 = json.load(open(D + "reviewer_sft/eval5_inputs.json"))
ap = {t: api(t) for t in ("opus45zero", "opus45fs", "sonnet55api")}
B = {"E14": {"key": k14, "amt": amounts(i14), "pred": {"Qwen3-4B fine-tuned": tuned(R + "reviewer_ft.json"), "Sonnet 5.5 (agents)": files("sonnet", "sv"), "Haiku 5.5 (agents)": {h: v for h, v in files("haiku", "rv").items() if h in k14}}},
     "E5": {"key": k5, "amt": amounts(i5), "pred": {"Qwen3-4B fine-tuned": tuned(R + "reviewer_e5ft.json"), "Sonnet 5.5 agents, run A": files("sonnetA", "xv"), "Sonnet 5.5 agents, run B": files("sonnetB", "xv"), "Sonnet 5.5 agents, run C": files("sonnetC", "xv"),
            "Sonnet 5.5 agents + 4 examples": files("sonnetfs", "xv"), "Haiku 5.5 (agents)": files("haikux", "xv"), "Sonnet 5.5 API (1 call per history)": ap["sonnet55api"][0], "Opus 4.5 API": ap["opus45zero"][0], "Opus 4.5 API + 4 examples": ap["opus45fs"][0]}},
     "tokens_api": {k: v[1] for k, v in ap.items()},
     "tuned_reasons_E5": {h: json.load(open(R + "reviewer_e5ft.json"))[h]["raw"][:600] for h in ("X0004",)},
     "text_E5": {h["history_id"]: h["text"] for h in i5 if h["history_id"] in ("X0004",)}}
json.dump(B, open("/Users/geboou/Desktop/oversight/finetune/entregable/data/predictions.json", "w"), ensure_ascii=False)
print({k: {c: len(p) for c, p in v["pred"].items()} for k, v in B.items() if k.startswith("E")}); print(B["tokens_api"])
