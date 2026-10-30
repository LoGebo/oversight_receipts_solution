"""Score classifier outputs on a synthetic benchmark. Usage: python3 score.py <set> <model> [<model> ...]  (audit_out/<model>_inNN.json)"""
import json, sys, glob, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
name, models = sys.argv[1], sys.argv[2:]
RESTR = {k for k, v in json.load(open("/Users/geboou/Desktop/oversight/explainers/09-video-maestro/facts.json"))["classifier"]["restricted"].items() if v}
X = {}
for l in open(HERE / f"{name}_expected.jsonl"):
    d = json.loads(l); X[d["line_id"]] = d
excl = {f["line_id"] for f in json.load(open(HERE / f"{name}_flagged_decontam.json"))}
def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** .5)
    return round((c - m) / d * 100, 1), round((c + m) / d * 100, 1)
for model in models:
    pred = {}
    for f in sorted(glob.glob(str(HERE / "audit_out" / f"{model}_in*.json"))):
        for r in json.load(open(f)):
            for l in r.get("lines", []): pred[l["line_id"]] = l
    ids = [i for i in X if i not in excl]
    n = len(ids); got = [i for i in ids if i in pred]
    ex = [i for i in got if pred[i]["category"] == X[i]["category"]]
    al = [i for i in got if pred[i]["category"] == X[i]["category"] or pred[i]["category"] in X[i]["acceptable_alternatives"]]
    rs = [i for i in got if (pred[i]["category"] in RESTR) == (X[i]["category"] in RESTR)]
    err = [i for i in got if i not in ex]
    low_err = [i for i in err if pred[i]["confidence"] == "low"]
    low_ok = [i for i in ex if pred[i]["confidence"] == "low"]
    print(f"== {model}: lines scored {n}, answered {len(got)}")
    print(f"  exact {len(ex)}/{len(got)} = {100*len(ex)/max(1,len(got)):.1f}% CI{wilson(len(ex),len(got))};  exact-or-alt {len(al)}/{len(got)} = {100*len(al)/max(1,len(got)):.1f}%;  restricted-flag acc {100*len(rs)/max(1,len(got)):.1f}%")
    print(f"  errors {len(err)}: rated low {len(low_err)} ({100*len(low_err)/max(1,len(err)):.0f}% caught by EXC-03); correct lines rated low (false alarms) {len(low_ok)}/{len(ex)} = {100*len(low_ok)/max(1,len(ex)):.1f}%")
    print("  confidence mix of errors:", dict(collections.Counter(pred[i]["confidence"] for i in err)))
    sl = collections.defaultdict(lambda: [0, 0])
    for i in got:
        sl[X[i]["slice"]][1] += 1; sl[X[i]["slice"]][0] += i in ex
    print("  by slice:", {k: f"{v[0]}/{v[1]}" for k, v in sorted(sl.items())})
    lg = collections.defaultdict(lambda: [0, 0])
    for i in got:
        lg[X[i]["language"]][1] += 1; lg[X[i]["language"]][0] += i in ex
    print("  by language:", {k: f"{v[0]}/{v[1]}" for k, v in sorted(lg.items())})
