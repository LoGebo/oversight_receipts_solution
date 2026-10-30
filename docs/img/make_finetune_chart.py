"""Fine-tuned vs base vs frontier on the SAME 58 validation histories. Reads real result files only.
Run: uv run --with matplotlib python make_finetune_chart.py"""
import json, math
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
F = "/Users/geboou/Desktop/oversight/finetune/v2/results/"
fr = json.load(open(F + "frontier_eval.json"))
def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return 100 * (c - h), 100 * (c + h)
def pair(d):
    r = d["history_recall"].split("/"); f = d["clean_false_alarms"].split("/")
    return (int(r[0]), int(r[1])), (int(f[0]), int(f[1]))
sys = []
for name, key, col in [("Claude Opus 4.5\n(frontier, zero-shot)", "anthropic/claude-opus-4.5", "#8a8985"),
                       ("Claude Sonnet 5.5\n(frontier, zero-shot)", "anthropic/claude-sonnet-5.5", "#8a8985"),
                       ("Qwen3.5-9B\nBEFORE tuning", "qwen/qwen3.5-9b", "#9cc3ee"),
                       ("Qwen3.5-27B\nBEFORE tuning", "qwen/qwen3.5-27b", "#9cc3ee")]:
    sys.append((name,) + pair(fr[key]) + (col,))
for name, f, col in [("Qwen3.5-9B\nAFTER tuning", "modal_Qwen3.5-9B_eval.json", "#2a78d6"), ("Qwen3.5-27B\nAFTER tuning", "modal_Qwen3.5-27B_eval.json", "#1b4f9c")]:
    sys.append((name,) + pair(json.load(open(F + f))) + (col,))
fig, axes = plt.subplots(1, 2, figsize=(15.5, 6.4), sharey=True)
fig.patch.set_facecolor("white")
for ax, idx, title, better in [(axes[0], 2, "False alarms on 26 clean months", "lower is better"), (axes[1], 1, "Recall: fraud months with a planted receipt escalated (32)", "higher is better")]:
    ys = list(range(len(sys)))[::-1]
    for y, s in zip(ys, sys):
        k, n = s[idx]; v = 100 * k / n; lo, hi = wilson(k, n)
        ax.barh(y, v, color=s[3], height=0.62)
        ax.errorbar(v, y, xerr=[[v - lo], [hi - v]], color="black", capsize=3, lw=1.1)
        ax.text(min(hi + 2, 101), y, f"{v:.0f}%  ({k}/{n})", va="center", fontsize=10)
    ax.set_xlim(0, 118); ax.set_yticks(ys); ax.set_yticklabels([s[0] for s in sys], fontsize=10)
    ax.set_title(f"{title}\n({better})", loc="left", fontsize=11.5, fontweight="bold")
    ax.set_xlabel("Percent (error bars: 95% Wilson interval)")
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
fig.text(0.01, 0.01, "Same 58 held-out validation histories, same prompt for every system. Frontier and 'before' models see the prompt once (no examples, no tuning); 'after' models were fine-tuned on 232 histories from the same authors.\nNot an independent exam: it favours the tuned models. Two 'before' outputs per Qwen model could not be parsed and count as no escalation.", fontsize=8.8, color="#52514e")
plt.tight_layout(rect=(0, 0.07, 1, 1)); plt.savefig("finetune_results.png", dpi=110, facecolor="white")
for s in sys: print(s[0].replace("\n", " "), s[1], s[2])
