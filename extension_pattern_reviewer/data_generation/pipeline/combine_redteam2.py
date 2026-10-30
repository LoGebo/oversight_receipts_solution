import json, glob, collections
from validator.engine import run_engine
from validator.normaliser import normalise_receipt
D = "/Users/geboou/Desktop/oversight/finetune/data_synth/"
out = []; bad = 0
for f in sorted(glob.glob(D + "redteam/rt2_[0-9].json")):
    for h in json.load(open(f)):
        recs, cats, gf = [], {}, {}
        for r in h["receipts"]:
            r = json.loads(json.dumps(r)); planted = r.pop("planted", False); g = r.pop("gift_for", None) or {}
            for li in r["line_items"]: cats[li["line_id"]] = li.pop("category")
            for k, v in g.items(): gf[k] = (v[0], v[1])
            r["_planted"] = planted; recs.append(r)
        res = run_engine([normalise_receipt({k: v for k, v in r.items() if k != "_planted"}) for r in recs], cats, gf or None, None)
        ok = True
        for r in recs:
            x = res[r["receipt_id"]]; r["_engine"] = {"disposition": str(x.disposition), "fired": sorted({c.rule_id for c in x.checks if c.status == "fired"})}
            ok &= str(x.disposition) == "pass"
        if not ok or not any(r["_planted"] for r in recs): bad += 1; continue
        planted = [r["receipt_id"] for r in recs if r.pop("_planted")]
        out.append({"scheme": h["scheme"], "family": h["scheme"], "reason": h["reason"], "language": h["language"], "split": "redteam2", "planted_receipts": planted,
                    "receipts": recs, "_cats": cats, "_gift_for": {k: list(v) for k, v in gf.items()}, "source_file": f.split("/")[-1]})
for i, h in enumerate(out): h["history_id"] = f"RU{i+1:03d}"
open(D + "patterns_v2_redteam2.jsonl", "w").write("\n".join(json.dumps(h, ensure_ascii=False) for h in out) + "\n")
print("histories kept", len(out), "dropped", bad, "receipts", sum(len(h["receipts"]) for h in out), "planted", sum(len(h["planted_receipts"]) for h in out),
      "schemes", len({h["scheme"] for h in out}))
