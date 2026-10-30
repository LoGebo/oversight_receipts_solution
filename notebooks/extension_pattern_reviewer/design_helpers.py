"""design_helpers: visual theme for the notebooks (validated palette, cards, banners, callouts, chart helpers).
Palette = the validated reference palette (categorical slots 1-4 pass the CVD/normal-vision gates; status colors reserved)."""
import matplotlib as mpl, matplotlib.pyplot as plt, numpy as np
from IPython.display import display, HTML as _HTML
def HTML(s):
    """HTML that Jupyter will not try to typeset as math (MathJax skips the tex2jax_ignore class)."""
    return _HTML('<div class="tex2jax_ignore">' + s + '</div>')
SafeHTML = HTML

PAL = dict(ft="#2a78d6", sonnet="#eb6834", opus="#1baf7a", haiku="#eda100", ai="#6250d6",
           good="#0ca30c", warn="#fab219", crit="#d03b3b", ink="#0b0b0b", ink2="#52514e", muted="#8a8985", grid="#e8e7e3", surface="#fcfcfb", soft="#f3f2ee")
ENTITY = {"Qwen": PAL["ft"], "Sonnet": PAL["sonnet"], "Opus": PAL["opus"], "Haiku": PAL["haiku"]}
def entity_color(label):
    for k, v in ENTITY.items():
        if label.startswith(k): return v
    return PAL["muted"]

def apply_theme():
    mpl.rcParams.update({
        "figure.dpi": 120, "figure.facecolor": PAL["surface"], "axes.facecolor": PAL["surface"], "savefig.facecolor": PAL["surface"],
        "axes.edgecolor": PAL["grid"], "axes.linewidth": 1, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.grid.axis": "y", "grid.color": PAL["grid"], "grid.linewidth": 1, "axes.axisbelow": True,
        "axes.titlelocation": "left", "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlecolor": PAL["ink"], "axes.titlepad": 12,
        "axes.labelcolor": PAL["ink2"], "axes.labelsize": 10, "xtick.color": PAL["ink2"], "ytick.color": PAL["ink2"], "xtick.labelsize": 9.5, "ytick.labelsize": 9.5,
        "text.color": PAL["ink"], "font.size": 10, "legend.frameon": False, "legend.fontsize": 9.5, "lines.linewidth": 2, "lines.solid_capstyle": "round",
    })

CSS = """
<style>
.nb{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif;color:#0b0b0b}
.nb-hero{background:linear-gradient(135deg,#0f2a4a 0%,#2a78d6 100%);color:#fff;border-radius:16px;padding:34px 38px;margin:6px 0 14px}
.nb-hero h1{margin:0 0 6px;font-size:30px;font-weight:800;letter-spacing:-.5px;color:#fff}
.nb-hero p{margin:4px 0;font-size:15px;opacity:.92;color:#fff}
.nb-banner{display:flex;align-items:center;gap:16px;border-left:6px solid #2a78d6;background:#f3f2ee;border-radius:0 12px 12px 0;padding:14px 20px;margin:26px 0 8px}
.nb-banner .n{font-size:30px;font-weight:800;color:#2a78d6;min-width:38px;line-height:1}
.nb-banner .t{font-size:20px;font-weight:750;line-height:1.2;color:#0b0b0b}
.nb-banner .q{font-size:13.5px;color:#52514e;margin-top:3px}
.nb-kpis{display:flex;flex-wrap:wrap;gap:12px;margin:10px 0}
.nb-kpi{flex:1 1 150px;min-width:140px;background:#fcfcfb;border:1px solid #e8e7e3;border-top:4px solid var(--c,#2a78d6);border-radius:10px;padding:12px 14px}
.nb-kpi .v{font-size:28px;font-weight:800;line-height:1.1;color:#0b0b0b}
.nb-kpi .l{font-size:12.5px;font-weight:650;color:#0b0b0b;margin-top:3px}
.nb-kpi .s{font-size:11.5px;color:#52514e;margin-top:2px}
.nb-call{border-radius:10px;padding:12px 16px;margin:12px 0;border:1px solid var(--c);background:var(--bg);color:#0b0b0b;font-size:14px;line-height:1.5}
.nb-call b.h{color:var(--c);letter-spacing:.2px;text-transform:uppercase;font-size:11.5px;display:block;margin-bottom:2px}
.nb-cards{display:flex;flex-wrap:wrap;gap:12px;margin:10px 0}
.nb-card{flex:1 1 220px;background:#fcfcfb;border:1px solid #e8e7e3;border-radius:12px;padding:14px 16px}
.nb-card .k{font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--c,#2a78d6)}
.nb-card .t{font-size:16px;font-weight:750;margin:3px 0 4px;color:#0b0b0b}
.nb-card .d{font-size:13px;color:#52514e;line-height:1.45}
.nb-pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:700;color:#fff}
</style>
"""
def setup():
    apply_theme(); display(_HTML(CSS))
    try:
        import pandas as pd
        from pandas.io.formats.style import Styler
        ip = get_ipython(); f = ip.display_formatter.formatters["text/html"]
        f.for_type(Styler, lambda st: '<div class="tex2jax_ignore">' + st.to_html() + '</div>')
        f.for_type(pd.DataFrame, lambda df: '<div class="tex2jax_ignore">' + df.to_html() + '</div>')
    except Exception as e: print("formatter not registered:", e)

def hero(title, subtitle, line3=""):
    display(HTML(f"<div class='nb nb-hero'><h1>{title}</h1><p>{subtitle}</p><p style='opacity:.75;font-size:13px'>{line3}</p></div>"))

def banner(n, title, question=""):
    display(HTML(f"<div class='nb nb-banner'><div class='n'>{n}</div><div><div class='t'>{title}</div><div class='q'>{question}</div></div></div>"))

def kpis(items):
    """items: [(value, label, sub, color)]"""
    h = "".join(f"<div class='nb-kpi' style='--c:{c}'><div class='v'>{v}</div><div class='l'>{l}</div><div class='s'>{s}</div></div>" for v, l, s, c in items)
    display(HTML(f"<div class='nb nb-kpis'>{h}</div>"))

KIND = {"learned": ("#2a78d6", "#eef4fc", "What we learned"), "good": ("#0a7a0a", "#eef8ee", "Demonstrated"), "warn": ("#9a6b00", "#fff6e0", "Careful"), "bad": ("#d03b3b", "#fdeeee", "Not demonstrated"), "idea": ("#6250d6", "#f1effc", "Idea")}
def callout(kind, html, title=None):
    c, bg, t = KIND[kind]
    display(HTML(f"<div class='nb nb-call' style='--c:{c};--bg:{bg}'><b class='h'>{title or t}</b>{html}</div>"))

def cards(items):
    """items: [(kicker, title, text, color)]"""
    h = "".join(f"<div class='nb-card' style='--c:{c}'><div class='k'>{k}</div><div class='t'>{t}</div><div class='d'>{d}</div></div>" for k, t, d, c in items)
    display(HTML(f"<div class='nb nb-cards'>{h}</div>"))

def pill(text, color): return f"<span class='nb-pill' style='background:{color}'>{text}</span>"

def finish(fig, ax=None):
    fig.tight_layout(); plt.show()

def label_bars(ax, bars, fmt="{:.0f}%", dy=1.2, fs=9):
    for b in bars:
        v = b.get_height(); ax.text(b.get_x() + b.get_width() / 2, v + dy, fmt.format(v), ha="center", va="bottom", fontsize=fs, color=PAL["ink"], fontweight="bold")

def round_bars(bars):
    from matplotlib.patches import FancyBboxPatch
    for b in bars:
        b.set_linewidth(0)


STATUS_CSS = {"pass": "background-color:#e6f6e6;color:#0a7a0a;font-weight:700", "review": "background-color:#fff3d6;color:#8a6200;font-weight:700", "flag": "background-color:#fbe6e6;color:#b02a2a;font-weight:700"}
def status_style(v): return STATUS_CSS.get(v, "")
def yes_no_style(v): return "color:#0a7a0a;font-weight:700" if v == "yes" else ("color:#b02a2a;font-weight:700" if v == "no" else "")

def pipeline_diagram():
    import matplotlib.patches as mp
    fig, ax = plt.subplots(figsize=(13, 3.1)); ax.axis("off"); ax.set_xlim(0, 13.2); ax.set_ylim(0, 3)
    steps = [("Receipts", "JSON,\nmany languages", PAL["muted"]), ("Normalizer", "cleans and\nvalidates", PAL["muted"]), ("Classifier", "LLM: a category\nper line", PAL["ai"]), ("Retriever", "which of the 41\nrules apply", PAL["muted"]), ("Engine", "37 checks,\nplain code", PAL["ft"]), ("Report", "pass · review\n· flag", PAL["good"])]
    w = 1.86; gap = .36
    for k, (t, d, col) in enumerate(steps):
        x = .15 + k * (w + gap)
        ax.add_patch(mp.FancyBboxPatch((x, .8), w, 1.5, boxstyle="round,pad=0.02,rounding_size=0.12", fc="white", ec=col, lw=2.2))
        ax.text(x + w / 2, 1.75, t, ha="center", va="center", fontsize=12.5, fontweight="bold", color=PAL["ink"])
        ax.text(x + w / 2, 1.2, d, ha="center", va="center", fontsize=9, color=PAL["ink2"], linespacing=1.3)
        if k < len(steps) - 1: ax.annotate("", xy=(x + w + gap - .04, 1.55), xytext=(x + w + .04, 1.55), arrowprops=dict(arrowstyle="-|>", color=PAL["ink2"], lw=1.6))
    ax.text(.15 + 2 * (w + gap) + w / 2, .42, "the only AI step", ha="center", fontsize=9.5, color=PAL["ai"], fontweight="bold")
    ax.text(.15 + 4 * (w + gap) + w / 2, .42, "computed, never judged", ha="center", fontsize=9.5, color=PAL["ft"], fontweight="bold")
    ax.set_title("The pipeline: five pieces, one of them uses AI"); plt.show()


def architecture_diagram(save=None):
    """Full system architecture: first line (deterministic, per receipt), second line (NEW: bounded LLM over the employee's history), offline lifecycle."""
    import matplotlib.patches as mp
    fig, ax = plt.subplots(figsize=(14.8, 10.2)); ax.axis("off"); ax.set_xlim(0, 15.5); ax.set_ylim(-.55, 10.2)
    W, H = 2.15, 1.38
    xs = [.5 + 2.4 * k for k in range(6)]

    def region(y0, y1, color, label, right=None, tag=None, lx=.5):
        ax.add_patch(mp.FancyBboxPatch((.25, y0), 15.0, y1 - y0, boxstyle="round,pad=0.02,rounding_size=0.18", fc=color, ec="none", alpha=.55, zorder=0))
        ax.text(lx, y1 - .26, label, fontsize=11.5, fontweight="bold", color=PAL["ink"], va="center", zorder=2)
        if right: ax.text(14.95, y1 - .26, right, fontsize=9.5, color=PAL["ink2"], va="center", ha="right", zorder=2, fontstyle="italic")
        if tag: ax.text(14.95, y1 - .26, tag, fontsize=9.5, fontweight="bold", color="white", va="center", ha="right", zorder=3, bbox=dict(boxstyle="round,pad=0.3", fc=PAL["ai"], ec="none"))

    def box(x, y, title, sub, ec, fc="white", w=W, h=H, lw=2.2):
        ax.add_patch(mp.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec=ec, lw=lw, zorder=2))
        ax.text(x + w / 2, y + h - .28, title, ha="center", va="center", fontsize=9.6, fontweight="bold", color=PAL["ink"], zorder=3)
        ax.text(x + w / 2, y + h / 2 - .18, sub, ha="center", va="center", fontsize=7.7, color=PAL["ink2"], linespacing=1.28, zorder=3)

    def arrow(p, q, color=None, ls="-", lw=1.7, rad=0.0, label=None, lpos=.5, loff=(0, .14), fs=8.2):
        ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-|>", color=color or PAL["ink2"], lw=lw, ls=ls, connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0), zorder=4)
        if label: ax.text(p[0] + (q[0] - p[0]) * lpos + loff[0], p[1] + (q[1] - p[1]) * lpos + loff[1], label, ha="center", va="bottom", fontsize=fs, color=color or PAL["ink2"], fontstyle="italic", zorder=5, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=.8))

    ax.text(.25, 9.95, "System architecture: two lines of defense, and how the second one is built and proven", fontsize=14, fontweight="bold", color=PAL["ink"], va="center")
    # ---------------- first line
    region(6.62, 9.62, "#e3eefb", "FIRST LINE · deterministic core, one receipt at a time (the original task)")
    y1 = 7.45
    box(xs[0], y1, "Receipts", "JSON, line items\nin 6 languages", PAL["muted"])
    box(xs[1], y1, "Normalizer", "validates and cleans\ncurrency, dates, numbers", PAL["muted"])
    box(xs[2], y1, "Classifier", "LLM: one category\nper line item\n(the only AI here)", PAL["ai"])
    box(xs[3], y1, "Retriever", "which of the 41 rules\napply to this receipt\n(37 predicates)", PAL["muted"])
    box(xs[4], y1, "Rule engine", "37 checks in plain code\nexceptions + signals\nverdict computed (EXC-01)", PAL["ft"])
    box(xs[5], y1, "Verdict", "", PAL["good"])
    for k in range(5): arrow((xs[k] + W, y1 + H / 2), (xs[k + 1] - .02, y1 + H / 2))
    for j, (t, c) in enumerate([("pass", PAL["good"]), ("review", PAL["warn"]), ("flag", PAL["crit"])]):
        ax.text(xs[5] + W / 2, y1 + .75 - j * .33 - .05, f"  {t}  ", ha="center", va="center", fontsize=9.2, fontweight="bold", color="white" if t != "review" else PAL["ink"], zorder=4, bbox=dict(boxstyle="round,pad=0.22", fc=c, ec="none"))
    # ---------------- second line
    region(3.25, 6.38, "#efecfb", "SECOND LINE · cross-receipt reviewer: a bounded LLM that can only escalate", tag="NEW", lx=2.15)
    y2 = 3.6
    box(xs[0], y2, "Employee month", "receipts that got pass\n+ the employee's other\nreceipts of the month", PAL["muted"])
    box(xs[1], y2, "Context builder", "plain code, no LLM:\ntotals by type, repeated\nmerchants, weekends,\ntrips, approval refs", PAL["ft"])
    box(xs[2], y2, "Pattern reviewer", "LLM, one bounded pass\nfrontier model today (API)\nor own Qwen3-4B + LoRA", PAL["ai"], fc="#f7f5fe")
    box(xs[3], y2, "Compact output", "JSON only:\n{receipt_id, reason}\none sentence each", PAL["muted"])
    box(xs[4], y2, "Escalate-only guard", "pass → review\nnever lowers a flag,\nnever rejects anything", PAL["ft"])
    box(xs[5], y2, "Final disposition", "engine verdict stays;\nescalations join the\nhuman review queue", PAL["good"])
    for k in range(5): arrow((xs[k] + W, y2 + H / 2), (xs[k + 1] - .02, y2 + H / 2))
    bus_y = 6.5
    ax.plot([xs[5] + .55, xs[5] + .55], [y1, bus_y], color=PAL["ink2"], lw=1.6, zorder=4); ax.plot([xs[5] + .55, xs[0] + 1.0], [bus_y, bus_y], color=PAL["ink2"], lw=1.6, zorder=4)
    arrow((xs[0] + 1.0, bus_y), (xs[0] + 1.0, y2 + H + .02))
    ax.text(7.3, bus_y + .04, "receipts whose verdict is \"pass\"", ha="center", va="bottom", fontsize=8.8, color=PAL["ink2"], fontstyle="italic", zorder=5)
    arrow((xs[5] + 1.6, y1), (xs[5] + 1.6, y2 + H + .02))
    ax.text(xs[5] + 1.5, 5.62, "\"flag\" and \"review\"\nkeep the engine's verdict", ha="right", va="center", fontsize=8.4, color=PAL["ink2"], fontstyle="italic", zorder=5, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=.8))
    # ---------------- offline lifecycle
    region(.2, 2.95, "#efeeea", "OFFLINE · how it is built and proven", right="never in the request path")
    y3 = .42; h3 = 1.5
    box(xs[0], y3, "Fraud schemes", "8 base families (code)\n48 red-team (Claude)\n16 independent (Opus)", PAL["muted"], h=h3)
    box(xs[1], y3, "Engine verification", "every receipt of every\nhistory must get pass\nfrom the real engine", PAL["ft"], h=h3)
    box(xs[2], y3, "Fine-tune", "SFT + LoRA on Qwen3-4B\n810 train · 42 valid\nMac mini 16 GB · ~5 h", PAL["ai"], h=h3)
    box(xs[3], y3, "Evaluation", "frozen criteria, scored\nby code, CI + bootstrap\nE1–E4 own · E5 blind", PAL["ft"], h=h3)
    box(xs[4], y3, "Go / no-go gate", "own model ships only if\nit beats the frontier on E5\ntoday: not met", PAL["crit"], h=h3, lw=2.6)
    box(xs[5], y3, "Pin and monitor", "weights + prompt + policy\nversioned together;\nrollback tested", PAL["muted"], h=h3)
    for k in range(5): arrow((xs[k] + W, y3 + h3 / 2), (xs[k + 1] - .02, y3 + h3 / 2))
    arrow((xs[2] + W / 2, y3 + h3 + .02), (xs[2] + W / 2, y2 - .02), color=PAL["ai"], ls=(0, (4, 3)), lw=1.9, label="LoRA weights", lpos=.8, loff=(.78, -.05))
    arrow((xs[4] + W / 2, y3 + h3 + .02), (xs[2] + W - .25, y2 - .02), color=PAL["crit"], ls=(0, (4, 3)), lw=1.7, rad=-.12, label="decides which\nreviewer runs", lpos=.3, loff=(0, .02))
    # legend (below)
    lx = 3.9; ly = -.3
    for j, (lab, col) in enumerate([("plain code", PAL["ft"]), ("LLM", PAL["ai"]), ("decision / output", PAL["good"]), ("data / process", PAL["muted"])]):
        ax.add_patch(mp.FancyBboxPatch((lx + j * 2.3, ly - .07), .24, .14, boxstyle="round,pad=0.01,rounding_size=0.03", fc="white", ec=col, lw=2, zorder=3)); ax.text(lx + j * 2.3 + .32, ly, lab, fontsize=9, va="center", color=PAL["ink2"])
    if save: fig.savefig(save, dpi=130, bbox_inches="tight")
    plt.show()
