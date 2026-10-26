# AI collaboration log

Concrete things the assistants got wrong, how it was caught, and what changed.

| # | What the AI got wrong | How it was caught | Outcome |
|---|---|---|---|
| A-001 | A research agent reported a Brex result as "94% vs 98%". | A separate fact-checking agent tried to refute the claim and could not confirm the 98% figure. | Dropped; only sourced numbers are quoted. |
| A-002 | The multi-agent plan said "~20 h" in several places while its own day-by-day table summed to ~22 h. | The completeness-critic agent recomputed the totals. | Plan uses the table, not the headline. |
| A-003 | The plan treated rule details (supersession, EXC-02 reading) as settled although the agents had only worked from summaries. | The critic flagged them as "digests not verified". | Rules are re-read from the policy files and each ambiguity becomes a logged decision. |

Assistants used: Claude Code (planning, research orchestration, code). Hand-checked: counts (32/79 receipts/lines, 28/65 scored, 9/16/3), the RCP-010 walkthrough against the policy text, and the answer-key split.
