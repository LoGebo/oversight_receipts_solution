"""Zero-shot comparison on the SAME 58 validation histories used for the fine-tuned models (v2/sft/valid.jsonl),
same system prompt and user text, through OpenRouter. Reads the key from validator/.env inside the process only.
  python3 frontier_eval.py                # all models
Output: results/frontier_eval.json (per-model metrics, raw outputs, spend from usage.cost)."""
import json, math, re, sys, time, urllib.request, concurrent.futures as cf
from pathlib import Path
HERE = Path(__file__).resolve().parent
ENV = Path("/Users/geboou/Desktop/oversight/validator/.env").read_text()
KEY = re.search(r"^OPENROUTER_API_KEY=(.+)$", ENV, re.M).group(1).strip()
MODELS = ["anthropic/claude-opus-4.5", "anthropic/claude-sonnet-5.5", "qwen/qwen3.5-9b", "qwen/qwen3.5-27b"]
CAP = 3.0
rows = [json.loads(l) for l in open(HERE / "sft" / "valid.jsonl")]

def call(model, msgs):
    body = {"model": model, "messages": msgs, "max_tokens": 3000, "temperature": 0}
    if model.startswith("qwen/"):
        body["reasoning"] = {"enabled": False}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    for a in range(3):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=180))
            return d["choices"][0]["message"].get("content") or "", (d.get("usage") or {}).get("cost", 0) or 0
        except Exception as e:
            err = repr(e)[:120]; time.sleep(3 + 4 * a)
    return "ERR " + err, 0

def parse(out):
    try:
        return {e["receipt_id"] for e in json.loads(out[out.index("{"):out.rindex("}") + 1])["escalate"]}
    except Exception:
        return None

def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]

res = {}; total = 0.0
for model in MODELS:
    if total > CAP: print("cap reached"); break
    with cf.ThreadPoolExecutor(8) as ex:
        outs = list(ex.map(lambda r: call(model, r["messages"][:2]), rows))
    spend = sum(o[1] for o in outs); total += spend
    tp = fp = fn = hit = fr = fa = cl = unp = 0; keep = []
    for r, (out, _) in zip(rows, outs):
        gold = {e["receipt_id"] for e in json.loads(r["messages"][2]["content"])["escalate"]}
        pred = parse(out); unp += pred is None; p = pred or set()
        tp += len(gold & p); fp += len(p - gold); fn += len(gold - p)
        if gold: fr += 1; hit += bool(gold & p)
        else: cl += 1; fa += bool(p)
        keep.append({"gold": sorted(gold), "pred": None if pred is None else sorted(pred), "raw": out[:200]})
    res[model] = {"history_recall": f"{hit}/{fr}", "recall_ci": wilson(hit, fr), "clean_false_alarms": f"{fa}/{cl}", "fa_ci": wilson(fa, cl),
                  "receipt_precision": round(tp / (tp + fp), 2) if tp + fp else None, "receipt_recall": round(tp / (tp + fn), 2),
                  "unparsed": unp, "spend_usd": round(spend, 4), "rows": keep}
    print(model, res[model]["history_recall"], res[model]["clean_false_alarms"], "unparsed", unp, "spend", round(spend, 4), flush=True)
    json.dump(res, open(HERE / "results" / "frontier_eval.json", "w"), indent=1)
print("total spend", round(total, 4))
