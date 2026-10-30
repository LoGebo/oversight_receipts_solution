"""Run a reviewer via the Anthropic Messages API on E5, one history per call. Usage: python3 run_api_reviewer.py <model_id> <tag> <zero|fewshot>
Key: read ANTHROPIC_API_KEY from validator/.env inside this process only (never printed, never written). Output: ../../results/api_<tag>.json {history_id: {escalate:[...], raw, usage}}"""
import json, sys, re, os, time, urllib.request, urllib.error, concurrent.futures as cf
D = "/Users/geboou/Desktop/oversight/finetune/data_synth/"
model, tag, mode = sys.argv[1:4]
DATASET = sys.argv[4] if len(sys.argv) > 4 else "eval5"          # eval5 (E5, 160) or eval14 (E1-E4, 275)
THINK = (sys.argv[5] == "think") if len(sys.argv) > 5 else False    # extended thinking (budget 4000 tokens)
key = None
for l in open("/Users/geboou/Desktop/oversight/validator/.env"):
    if l.startswith("ANTHROPIC_API_KEY="): key = l.split("=", 1)[1].strip().strip('"').strip("'")
assert key, "no key"
task = open(D + ("review_in/REVIEWER_TASK_FEWSHOT.md" if mode == "fewshot" else "review_in/REVIEWER_TASK.md")).read()
task = re.sub(r"## Hard rules.*?## What you may do", "## What you may do", task, flags=re.S)
task = re.sub(r"## Output.*?(?=\n## Worked examples|\Z)", "## Output\nReply with ONLY one JSON object for the history you are given: {\"history_id\": \"<id>\", \"escalate\": [{\"receipt_id\": \"<id>\", \"reason\": \"<one sentence>\"}, ...]}. Valid JSON only, no other text.\n", task, flags=re.S)
inp = json.load(open(D + ("reviewer_sft/eval5_inputs.json" if DATASET == "eval5" else "reviewer_sft/eval_inputs.json")))
def call(e):
    pay = {"model": model, "max_tokens": 6000, "system": task, "messages": [{"role": "user", "content": e["text"]}]}
    if THINK: pay["thinking"] = {"type": "enabled", "budget_tokens": 4000}; pay["max_tokens"] = 9000
    elif not model.startswith(("claude-sonnet-5", "claude-opus-5", "claude-haiku-5", "claude-fable")): pay["temperature"] = 0   # only the 5.x family rejects the temperature parameter (the old "-5-" test also matched claude-opus-4-5)
    body = json.dumps(pay).encode()
    for att in range(5):
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", body, {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=400)); raw = "".join(b.get("text", "") for b in r["content"] if b.get("type") == "text"); m = re.search(r"\{.*\}", raw, re.S)
            try: esc = [x["receipt_id"] for x in json.loads(m.group(0)).get("escalate", [])]; ok = True
            except Exception: esc, ok = [], False
            return e["history_id"], {"escalate": esc, "json_ok": ok, "raw": raw, "usage": r.get("usage")}
        except urllib.error.HTTPError as ex:
            if ex.code in (429, 500, 529): time.sleep(5 * (att + 1)); continue
            return e["history_id"], {"escalate": [], "json_ok": False, "raw": f"HTTP {ex.code}: {ex.read()[:200].decode(errors='replace')}"}
        except Exception as ex: time.sleep(3)
    return e["history_id"], {"escalate": [], "json_ok": False, "raw": "failed"}
out = {}
with cf.ThreadPoolExecutor(6) as ex:
    for hid, v in ex.map(call, inp): out[hid] = v
json.dump(out, open(D + f"../results/api_{tag}.json", "w"), ensure_ascii=False)
bad = sum(not v["json_ok"] for v in out.values()); tin = sum((v.get("usage") or {}).get("input_tokens", 0) for v in out.values()); tout = sum((v.get("usage") or {}).get("output_tokens", 0) for v in out.values())
print(tag, "done", len(out), "histories; invalid/failed", bad, "; tokens in", tin, "out", tout)
