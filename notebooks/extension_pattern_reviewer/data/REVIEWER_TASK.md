# Task: act as the second-line reviewer of an expense-policy engine (blind)
You get employee-month histories. A deterministic engine already checked EACH receipt on its own and passed it. Your job is the part the engine cannot see: PATTERNS ACROSS RECEIPTS of the same employee.

## Hard rules
- Read ONLY this file and your input file `/Users/geboou/Desktop/oversight/finetune/data_synth/review_in/<rvNN>.json`. Open nothing else in the project (no keys, labels, or other folders). No network, no git. Do not write scripts that guess; read each history and judge it yourself.
- Write ONLY your output file `/Users/geboou/Desktop/oversight/finetune/data_synth/review_out/<MODEL>_<rvNN>.json`.

## What you may do
You may only ESCALATE receipts to a human reviewer. You can never reject anything, and the engine's verdict stays `pass`. Escalate only the receipts that form a suspicious pattern, and give a short reason (one sentence).
Most histories are ordinary. Escalating a normal history wastes a human's time, so stay quiet when the history looks normal; if nothing is suspicious return an empty list.

## Policy digest (so you know the limits the engine enforces per receipt)
- A gift to a client: at most $50 per named recipient per receipt; a gift of $10 or more must name its recipient; cards and small tokens under $10 need no named recipient.
- Computer accessories: at most $200 per item unless a pre-approval reference (PA-...) is attached.
- Receipts above $75 must be itemized.
- Meals: per person per day at most $75 (APAC $60). Team meals above $150 need attendees documented. Individual meals, lodging and other travel must belong to a trip (trip id).
- Over-the-counter health items: at most $25 per trip. Personal care and clothing: a shared allowance of $150.
- Receipts between 00:00 and 05:00, alcohol, tobacco, gambling, personal electronics are handled by other rules.
Look for patterns across receipts that suggest circumventing a limit, double-claiming, claims that do not fit the declared trip, relationship, headcount or items, hidden personal spending, or anything else unusual. The SUMMARIES block was computed by code to help you; it is not a verdict.

## Output
A JSON list with one object per history in your input, in order:
{"history_id": "H001", "escalate": [{"receipt_id": "H001-R04", "reason": "<one sentence>"}, ...]}
Valid JSON only. Reply with one line: file path and the number of histories with at least one escalation.
