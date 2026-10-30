"""Cost per 1,000 reviewed employee-months. Measured = OpenRouter usage.cost on the 58 validation histories.
Estimated = rented-GPU time of our own (unbatched) evaluation harness x an unverified A100-80GB price. Run: uv run --with matplotlib python make_cost_chart.py"""
import json
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
fr = json.load(open("/Users/geboou/Desktop/oversight/finetune/v2/results/frontier_eval.json"))
per = lambda k: fr[k]["spend_usd"] / 58 * 1000
GPU_H = 2.50  # USD per hour, A100 80GB, UNVERIFIED list price
tuned9 = 11 / 58 * 60 / 3600 * GPU_H * 1000   # ~11 min for 58 histories (approx., from run timestamps)
tuned27 = 24 / 58 * 60 / 3600 * GPU_H * 1000  # ~24 min for 58 histories
rows = [("Claude Opus 4.5 (API)", per("anthropic/claude-opus-4.5"), "measured", "#8a8985"),
        ("Claude Sonnet 5.5 (API)", per("anthropic/claude-sonnet-5.5"), "measured", "#8a8985"),
        ("Qwen3.5-27B untuned (API, price proxy)", per("qwen/qwen3.5-27b"), "measured", "#9cc3ee"),
        ("Qwen3.5-9B untuned (API, price proxy)", per("qwen/qwen3.5-9b"), "measured", "#9cc3ee"),
        ("Qwen3.5-27B tuned, own GPU (est., unbatched)", tuned27, "estimated", "#1b4f9c"),
        ("Qwen3.5-9B tuned, own GPU (est., unbatched)", tuned9, "estimated", "#2a78d6")]
fig, ax = plt.subplots(figsize=(13, 5.2)); fig.patch.set_facecolor("white")
for i, (n, v, kind, c) in enumerate(rows):
    ax.barh(i, v, color=c, hatch="//" if kind == "estimated" else None, edgecolor="white" if kind == "estimated" else c, height=0.6)
    ax.text(v * 1.08, i, f"\\${v:,.2f}  ({kind})", va="center", fontsize=10)
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], fontsize=10)
ax.set_xscale("log"); ax.set_xlim(0.1, 80); ax.set_xlabel("USD per 1,000 reviewed employee-months (log scale)")
ax.set_title("Cost to review 1,000 employee-months", loc="left", fontsize=12.5, fontweight="bold")
for sp in ("top", "right"): ax.spines[sp].set_visible(False)
fig.text(0.01, 0.01, "Measured = OpenRouter usage.cost on the 58 validation histories. Estimated = rented-GPU minutes of our own unbatched evaluation x \\$2.50/h\n(unverified A100-80GB price); batching or vLLM would be much cheaper (not measured). One-off training: about 15 min (9B) and 40 min (27B) on one A100,\nroughly \\$0.6 and \\$1.7 at that price (estimate). A GPU kept on 24/7 has a fixed monthly cost that an API does not.", fontsize=8.6, color="#52514e")
plt.tight_layout(rect=(0, 0.13, 1, 1)); plt.savefig("cost_comparison.png", dpi=110, facecolor="white")
for r in rows: print(r[0], round(r[1], 2), r[2])
