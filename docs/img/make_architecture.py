import json, math
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.patches as mp
OUT="/Users/geboou/Desktop/oversight/validator/docs/img/"  # run: uv run --with matplotlib python make_architecture.py
BL="#2a78d6"; PU="#6250d6"; GR="#8a8985"; INK="#0b0b0b"; INK2="#52514e"; GOOD="#0ca30c"; CRIT="#d03b3b"; WARN="#fab219"
plt.rcParams["font.family"]="DejaVu Sans"

# ---------- Figure 1
fig,ax=plt.subplots(figsize=(14,12.1)); ax.axis("off"); ax.set_xlim(0,14); ax.set_ylim(0,12.1)
def region(y0,y1,c,label):
    ax.add_patch(mp.FancyBboxPatch((.2,y0),13.6,y1-y0,boxstyle="round,pad=0.02,rounding_size=0.15",fc=c,ec="none",alpha=.6,zorder=0))
    ax.text(.4,y1-.28,label,fontsize=13,fontweight="bold",color=INK,va="center")
def box(x,y,w,h,t,s,ec,fc="white",lw=2.4):
    ax.add_patch(mp.FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.02,rounding_size=0.1",fc=fc,ec=ec,lw=lw,zorder=2))
    ax.text(x+w/2,y+h-.27,t,ha="center",va="center",fontsize=11,fontweight="bold",color=INK,zorder=3)
    ax.text(x+w/2,y+(h-.5)/2,s,ha="center",va="center",fontsize=9,color=INK2,linespacing=1.3,zorder=3)
def arr(p,q,c=INK2,ls="-",lw=1.8,rad=0):
    ax.annotate("",xy=q,xytext=p,arrowprops=dict(arrowstyle="-|>",color=c,lw=lw,ls=ls,connectionstyle=f"arc3,rad={rad}",shrinkA=0,shrinkB=0),zorder=4)
def lab(x,y,t,c=INK2,ha="center",fs=9.6):
    ax.text(x,y,t,ha=ha,va="center",fontsize=fs,color=c,fontstyle="italic",zorder=5,bbox=dict(boxstyle="round,pad=0.12",fc="white",ec="none",alpha=.9))
ax.text(.2,11.85,"Architecture: the validator, its evaluation, and the pattern-reviewer extension",fontsize=15.5,fontweight="bold",color=INK,va="center")
# row 1 required pipeline
region(6.75,11.45,"#e3eefb","1 · REQUIRED PIPELINE  (one receipt at a time)")
W=2.0;H=1.85;g=.2;y=8.5
xs=[.4+k*(W+g) for k in range(6)]
items=[("Receipt","JSON, line items,\nmany languages",GR),("Normaliser","Unicode (NFKC) +\nwhitespace cleanup\nof item text;\nraw text kept",BL),("Item classifier","LLM via OpenRouter,\ncached; category,\nrestricted flag,\nconfidence band,\ngift recipient",PU),("Policy retriever","picks the rules\nthat apply to\nthis receipt",BL),("Policy engine","deterministic checks\nEXC-01 disposition\nno LLM verdict",BL),("Reporter","report.jsonl\n+ Streamlit viewer\npass/review/flag",BL)]
for x,(t,s,c) in zip(xs,items): box(x,y,W,H,t,s,c)
for k in range(5): arr((xs[k]+W,y+H/2),(xs[k+1]-.01,y+H/2))
# data box + fail-closed
box(6.8,6.95,2.4,1.0,"Policy documents (9)","+ category taxonomy",GR,fc="#f4f4f2",lw=2.4)
arr((8.0,7.97),(8.0,y-.01),c=GR)
ax.plot([6.8,6.3],[7.45,7.45],color=GR,lw=1.8,zorder=4); arr((6.3,7.45),(6.3,y-.01),c=GR)
lab(6.0,7.8,"taxonomy only",c=GR,fs=9)
ax.plot([9.2,9.6],[7.45,7.45],color=GR,lw=1.8,zorder=4); arr((9.6,7.45),(9.6,y-.01),c=GR)
lab(9.9,7.8,"rule text",c=GR,fs=9)
yf=y+H+.38
ax.plot([xs[2]+W/2,xs[2]+W/2],[y+H,yf],color=CRIT,lw=1.8,ls=(0,(4,3)),zorder=4)
ax.plot([xs[2]+W/2,xs[4]+W/2],[yf,yf],color=CRIT,lw=1.8,ls=(0,(4,3)),zorder=4)
arr((xs[4]+W/2,yf),(xs[4]+W/2,y+H+.01),c=CRIT,ls=(0,(4,3)))
lab((xs[2]+xs[4])/2+W/2,yf,"model error / timeout \u2192 review (fail closed)",c=CRIT,fs=9.6)
# row 2 evaluation
region(3.55,6.45,"#efeeea","2 · EVALUATION")
y2=4.05;H2=1.5
box(xs[0],y2,W,H2,"Answer key","expected labels,\nkept separate,\nnever an input",GR,fc="#f4f4f2")
box(xs[2],y2,W,H2,"Keyword baseline","regex/keywords\ninstead of the LLM\nclassifier",BL)
box(xs[3],y2,W,H2,"Oracle","true categories fed\nto the same engine:\nconsistency check",BL)
box(xs[4],y2,W,H2,"Scorer","disposition and\ncategory accuracy,\ncost per model",BL)
ya=3.82
ax.plot([xs[0]+W/2,xs[0]+W/2],[y2,ya],color=GR,lw=1.8,ls=(0,(4,3)),zorder=4)
ax.plot([xs[0]+W/2,xs[4]+W/2],[ya,ya],color=GR,lw=1.8,ls=(0,(4,3)),zorder=4)
arr((xs[4]+W/2,ya),(xs[4]+W/2,y2-.01),c=GR,ls=(0,(4,3)))
lab(xs[2]+W/2,ya,"answer key goes only to the scorer",c=GR)
arr((xs[2]+W/2,y2+H2),(xs[2]+W/2,y+.0),c=BL,ls=(0,(4,3)))
arr((xs[4]+W/2,y),(xs[4]+W/2,y2+H2+.0),c=BL,ls=(0,(4,3)))
lab(xs[4]+W/2+.0,6.4,"verdicts",c=BL)
lab(xs[2]+W/2,6.4,"swap classifier",c=BL)
# row 3 extension
region(.55,3.25,"#efecfb","3 · EXTENSION  (second line: employee-month patterns)")
y3=.75;H3=1.75
box(xs[0],y3,W,H3,"Employee-month","all receipts of one\nemployee + the\nengine verdicts",GR)
box(2.9,y3,2.4,H3,"Pattern reviewer","fine-tuned small open\nmodel (Qwen,\nLoRA/QLoRA)\nreads the month",PU)
box(5.6,y3,2.4,H3,"Escalate-only guard","may only raise\npass → review;\nnever lowers a flag",BL)
arr((xs[0]+W,y3+H3/2),(2.89,y3+H3/2)); arr((5.3,y3+H3/2),(5.59,y3+H3/2))
box(8.3,y3,2.7,H3,"Synthetic fraud data","fraud written by several\nmodel families, kept only if\nthe deterministic engine\nmarks every receipt PASS",PU)
box(11.25,y3,2.35,H3,"Training","LoRA fine-tune\nof a small open model",PU)
arr((11.0,y3+H3/2),(11.24,y3+H3/2),c=PU)
ax.annotate("",xy=(4.1,y3+H3+.02),xytext=(12.42,y3+H3+.02),arrowprops=dict(arrowstyle="-|>",color=PU,lw=1.8,ls=(0,(4,3)),connectionstyle="angle,angleA=90,angleB=0,rad=0",shrinkA=0,shrinkB=0),zorder=4)
lab(8.6,2.78,"trained weights",c=PU)
# engine verdicts: reporter -> employee-month (elbow)
xr=xs[5]+W/2; yb=3.4
ax.plot([xr,xr],[y,yb],color=INK2,lw=1.8,zorder=4)
ax.plot([xr,xs[0]+W/2],[yb,yb],color=INK2,lw=1.8,zorder=4)
arr((xs[0]+W/2,yb),(xs[0]+W/2,y3+H3+.02))
lab(7.0,yb,"engine verdicts per receipt  →  month grouped by employee",fs=9.6)
# legend
lx=3.6
for j,(l,c) in enumerate([("code / deterministic",BL),("LLM",PU),("data / answer key",GR)]):
    ax.add_patch(mp.FancyBboxPatch((lx+j*2.9,.17),.3,.16,boxstyle="round,pad=0.01,rounding_size=0.03",fc="white",ec=c,lw=2.2,clip_on=False))
    ax.text(lx+j*2.9+.4,.25,l,fontsize=10.5,va="center",color=INK2)
fig.savefig(OUT+"architecture.png",dpi=114,bbox_inches="tight",facecolor="white")
plt.close(fig)

