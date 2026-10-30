"""Results figure for the README. Reads real files only. Run: uv run --with matplotlib python make_results.py"""
import json, math
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
R = "/Users/geboou/Desktop/oversight/validator/"
F = "/Users/geboou/Desktop/oversight/finetune/v2/results/"
BL, GR, OR = "#2a78d6", "#8a8985", "#e69f00"

def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return 100 * (c - h), 100 * (c + h)

cmp = json.load(open(R + "output/compare/summary.json"))["models"]
short = {"openai/gpt-6-luna": "GPT-6\nLuna", "openai/gpt-oss-safeguard-20b": "gpt-oss-\nsafeguard-20b",
         "deepseek/deepseek-v4.1-flash": "DeepSeek\nV4.1 Flash", "anthropic/claude-haiku-5.5": "Claude\nHaiku 5.5"}
cmp.sort(key=lambda m: m["spend_usd"])

def ev(name):
    d = json.load(open(F + f"modal_Qwen3.5-{name}_eval.json"))
    r = int(d["history_recall"].split("/")[0]); rn = int(d["history_recall"].split("/")[1])
    f = int(d["clean_false_alarms"].split("/")[0]); fn = int(d["clean_false_alarms"].split("/")[1])
    return r, rn, f, fn
r9, rn9, f9, fn9 = ev("9B"); r27, rn27, f27, fn27 = ev("27B")

fig, (a, b) = plt.subplots(1, 2, figsize=(16, 7.2), gridspec_kw={"width_ratios": [1, 1.25]})
fig.patch.set_facecolor("white")
# A
xs = range(len(cmp))
cols = [OR if m["category_acc"][0] < m["category_acc"][1] else BL for m in cmp]
a.bar(xs, [m["spend_usd"] for m in cmp], color=cols, width=0.6)
for i, m in enumerate(cmp):
    a.text(i, m["spend_usd"] + 0.0003, f"${m['spend_usd']:.4f}\nlines {m['category_acc'][0]}/{m['category_acc'][1]}\ndisp. {m['disposition_acc'][0]}/{m['disposition_acc'][1]}", ha="center", va="bottom", fontsize=10)
a.set_xticks(list(xs)); a.set_xticklabels([short.get(m["model"], m["model"]) for m in cmp], fontsize=10)
a.set_ylabel("Cost in USD per 32-receipt run"); a.set_ylim(0, 0.0185)
a.set_title("A. Same engine, different classifier\n(32 receipts, 28 scored): dispositions are 28/28 for every model", loc="left", fontsize=12, fontweight="bold")
a.text(0, -0.2, "Orange = the only model with line-category errors in this run (63/65); the other three get 65/65.", transform=a.transAxes, fontsize=9, color="#52514e")
for s in ("top", "right"): a.spines[s].set_visible(False)
# B
groups = [("False-alarm rate on clean months\n(lower is better)", [(96.9, wilson(62, 64), "v1 4B, independent exam (E5)\n62/64", GR), (100 * f9 / fn9, wilson(f9, fn9), f"v2 Qwen3.5-9B\n{f9}/{fn9}", BL), (100 * f27 / fn27, wilson(f27, fn27), f"v2 Qwen3.5-27B\n{f27}/{fn27}", "#6250d6")]),
          ("Recall on fraud months\n(higher is better)", [(80.0, (71, 87), "v1 4B, independent exam (E5)\n~77/96", GR), (100 * r9 / rn9, wilson(r9, rn9), f"v2 Qwen3.5-9B\n{r9}/{rn9}", BL), (100 * r27 / rn27, wilson(r27, rn27), f"v2 Qwen3.5-27B\n{r27}/{rn27}", "#6250d6")])]
w = 0.26
for gi, (title, bars) in enumerate(groups):
    for bi, (val, (lo, hi), lab, col) in enumerate(bars):
        x = gi + (bi - 1) * (w + 0.03)
        b.bar(x, val, w, color=col, label=lab.split("\n")[0] if gi == 0 else None)
        b.errorbar(x, val, yerr=[[val - lo], [hi - val]], color="black", capsize=4, lw=1.2)
        b.text(x, hi + 2, f"{val:.0f}%\n{lab.split(chr(10))[1]}", ha="center", va="bottom", fontsize=9)
b.set_xticks([0, 1]); b.set_xticklabels([g[0] for g in groups], fontsize=10)
b.set_ylim(0, 128); b.set_ylabel("Percent"); b.legend(loc="upper center", ncol=3, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 1.0))
b.set_title("B. Pattern reviewer: false alarms and recall", loc="left", fontsize=12, fontweight="bold", pad=22)
b.text(0, -0.2, "Different exams, not comparable: v1 = independent exam by another author (E5);\nv2 = validation on held-out schemes by the same authors. Error bars: 95% Wilson intervals.\nThe larger model did not improve recall and raised false alarms.", transform=b.transAxes, fontsize=9, color="#52514e", va="top")
for s in ("top", "right"): b.spines[s].set_visible(False)
plt.tight_layout(rect=(0, 0.06, 1, 1)); plt.savefig("results.png", dpi=110, facecolor="white")
