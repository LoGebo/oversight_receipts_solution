"""Claude family route (agents, no CLI): `emit` writes one prompt file per history; the agent writes the answer JSON next to it; `ingest` validates it with the same checks as gen.py.
  python3 claude_route.py emit --cls fraud --n 8 --seed 700 --dir cl
  python3 claude_route.py ingest --dir cl --out out"""
import argparse, json, random, sys
from pathlib import Path
import gen, skeleton as SK
def emit(a):
    d = Path(a.dir); d.mkdir(exist_ok=True)
    for idx in range(a.n):
        rng = random.Random(a.seed * 1000 + idx); sk = SK.sample(rng, a.cls); hid = f"CL{a.cls[0].upper()}{a.seed:03d}{idx:03d}"
        domain, mech, decoy = gen.DOMAINS[(idx + a.seed) % len(gen.DOMAINS)], gen.MECHS[(idx * 3 + a.seed) % len(gen.MECHS)], gen.DECOYS[(idx + a.seed) % len(gen.DECOYS)]
        (d / f"{hid}.prompt.txt").write_text(gen.prompt(sk, domain, mech, decoy)); (d / f"{hid}.skeleton.json").write_text(json.dumps({"sk": sk, "domain": domain, "mechanism": mech, "decoy": decoy if a.cls == "clean" else None}))
    print("emitted", a.n, "prompts in", d)
def ingest(a):
    d = Path(a.dir); ok = []; bad = []
    for sf in sorted(d.glob("*.skeleton.json")):
        hid = sf.name.split(".")[0]; af = d / f"{hid}.answer.json"
        if not af.exists(): continue
        meta = json.loads(sf.read_text()); out = gen.extract_json(af.read_text())
        if not out: bad.append((hid, "no JSON")); continue
        h, err = gen.build(meta["sk"], out, hid)
        if not err: err = gen.engine_errors(h)
        if err: bad.append((hid, "; ".join(err)[:500])); continue
        h["meta"] = {"model": "claude-agent", "family": "claude", "domain": meta["domain"], "mechanism": meta["mechanism"], "decoy": meta["decoy"], "attempts": 1}; ok.append(h)
    Path(a.out).mkdir(exist_ok=True); json.dump(ok, open(Path(a.out) / f"claude_{d.name}.json", "w"), ensure_ascii=False)
    print(f"{len(ok)} valid, {len(bad)} rejected"); [print("REJECT", h, e[:300]) for h, e in bad[:10]]
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["emit", "ingest"]); ap.add_argument("--cls", default="fraud"); ap.add_argument("--n", type=int, default=8); ap.add_argument("--seed", type=int, default=700); ap.add_argument("--dir", default="cl"); ap.add_argument("--out", default="out")
    a = ap.parse_args(); (emit if a.mode == "emit" else ingest)(a)
