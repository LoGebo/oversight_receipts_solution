# Expense Policy Validator

Reads itemized expense receipts, classifies every line item, applies the written expense policy with a **deterministic rule engine**, and reports each exception with the rule and the policy text behind it. Disposition: `flag`, `review` or `pass`.

```
receipt → Normaliser → Item classifier (LLM, cached) → Policy retriever → Policy engine (plain code) → Reporter
                                                                                   ↑ EXC-01 disposition is code, never a model decision
```

## Run it
```
uv sync --group dev --group viewer
uv run python -m validator.run                      # offline, from the committed cache: no key, no network → output/report.jsonl
uv run pytest                                       # 971 tests
uv run --group viewer streamlit run viewer/app.py   # viewer: receipt list, receipt detail, metrics
uv run python -m validator.evaluation.evaluate      # regenerates output/EVAL.md (reads the answer key, evaluation only)
```
Live classification needs `ANTHROPIC_API_KEY` or `OPENROUTER_API_KEY` in `.env` (see `.env.example`; never committed) and an explicit `--out`, so a live run can never overwrite the committed results: `uv run python -m validator.run --provider openrouter --out output/live`. `scripts/compare_models.py` runs the classifier with several OpenRouter models side by side (own cache and output per model, spend cap).

## Architecture
- **Normaliser** (deterministic): Unicode NFKC, control characters removed, whitespace collapsed; `description_raw` is never changed. Translation belongs to the classifier (it returns an English rendering in the same call).
- **Item classifier**: `openai/gpt-oss-safeguard-20b` through OpenRouter, prompt v3. One call per receipt returns category (21 taxonomy categories), restricted flag, a confidence band and the stated recipient of gifts. Cached by sha256 of model + prompt + content, so re-runs cost nothing.
- **Retriever**: a table of predicates over items, MCC and metadata (37 rows); no vector database. A rule the retriever misses raises an error instead of being skipped.
- **Engine**: pure Python. USD thresholds, carve-outs that need recorded evidence, regional overrides (APAC beats global), cross-receipt rules (MEAL-01, REG-03), EXC-01 disposition. 41 rules, 37 with their own check. The four timing rules (TIME-01..04) are implemented and resolve the four stretch receipts correctly; they are not scored, as the brief says.
- **Reporter**: copies the exact policy text and line ids for every finding.

## Prompts
The classifier prompt contains the taxonomy text only, never the answers. It returns JSON: category, band (`high`/`medium`/`low`), English rendering, recipient. v1→v3 were compared on a 144-line held-out set written independently of the dataset; v3 was kept because it extracts gift recipients, which a rule needs (RCP-022), with no loss in exact accuracy on `high` lines (109/109). Temperature 0 where the model accepts it; reproducibility comes from the committed cache keyed by model, prompt and content.

## Policy engine
One module per policy document (`src/validator/rules/`), each rule citing its id. Boundaries follow the text exactly (`$189` dock passes, `$329` monitor without pre-approval does not). A carve-out never applies without its recorded evidence (RCP-027). **EXC-03 threshold:** confidence below **0.5** (band `low` = 0.3; `medium` = 0.7; `high` = 0.9, ordinal, not calibrated) removes the line from every rule and raises a review signal. It fired 0 times on the dataset.

## Evaluation (28 scored receipts, 65 lines; `output/EVAL.md`)
| | A LLM | B ORACLE (perfect categories) | C KEYWORD |
|---|---|---|---|
| Disposition accuracy | 28/28 | 27/28 | 21/28 |
| False positives (of 9 pass) / missed (of 16 flag) | 0 / 0 | 0 / 1 | 1 / 4 |
| Macro F1 / restricted F1 | 1.000 / 1.000 | gold | 0.776 / 0.821 |

Where it holds and where it does not: 28 receipts is tiny (a perfect score has a 95% lower bound of 87.7%). The engine was written with these receipts and answers in view, so B is a consistency check, not a generalisation estimate; only the classifier is measured blind, and the taxonomy's own examples sit in its prompt. On the independent held-out set the classifier scores 137/144 exact (95.1%). Per-rule precision/recall, exact line citation (26/26) and the four timing receipts (4/4) are in `EVAL.md`.
**Failure cases.** (1) RCP-022 under B: with perfect categories the engine passes it, because who received the items is stated only in the text; the classifier's recipient output is what fires GIFT-04, so a perfect category score would not have caught it (stage: classification). (2) Held-out lines such as "Gel hydroalcoolique" → `health_otc` where the annotator says `personal_care`; 3 of 7 errors are rated `low` and reach EXC-03.
**Base rate.** The dataset is 57% violations; a real stream has a few percent. With 0 false flags seen in only 12 non-flag receipts, the true false-alarm rate could be up to 26.5% (95% bound), which at 3% prevalence would make as few as 8.5% of flags real. So 0/9 false positives says little about what reviewers would see. Before production I would measure precision on a random sample at the real rate, per-rule precision, and the calibration of the confidence bands.

## Key decisions
Answer key physically split from the pipeline, enforced by a test; all 32 receipts processed (group rules need context), 28 scored; the baseline frozen by hash before scoring; the disposition and every threshold in code, the model only classifies; fail closed (a model error gives `review`, never `pass`); a one-page AWS design with the cost recomputed from measured tokens. Full log: `DECISIONS.md`.

## Extension: cross-receipt pattern reviewer (beyond the brief)
The engine judges one receipt at a time, so it cannot see schemes that only show across a month (spend split under a cap, a pre-approval reused, a stay longer than the trip). I added a second-line LLM that reads an employee-month and may **only escalate `pass → review`**; the engine keeps the verdict. Fraud histories that the engine passes were generated synthetically (several model families, validated by the real engine) and a small local model was fine-tuned on them.
**Results so far, kept as they are:** v1 (Qwen3-4B, MLX LoRA) looked strong on its own generator (88% recall, 0% false alarms) but on an independent exam by another author it reached 80% recall with 97% false alarms, and a counterfactual showed it had learned a weekend shortcut. v2 data (290 histories, code-controlled sampler, several authors) lowers the shortcut but the anti-shortcut gate still fails (surface-feature AUROC 0.657, target ≤ 0.60). **v2 result so far (validation on 58 held-out histories, same authors as the training data):** Qwen3.5-9B, QLoRA, loss on the answer only: at least one planted receipt escalated in 25/32 fraud histories (78%, 95% CI 61–89%), 2/26 false alarms on clean months (7.7%, CI 2–24%); receipt-level precision 0.93, recall 0.72; 5 of 58 outputs could not be parsed. This is not an independent exam, so it supports "much better than v1 on false alarms" and nothing about frontier models. Qwen3.5-27B: *(pending)*. No claim to beat frontier models is made. Notebooks: `notebooks/`; code, data and logs: `extension_pattern_reviewer/`.

## Data, services and spend
Synthetic data. Receipts and policy text are sent to **OpenRouter** (the key Oversight provided), which routes the classifier calls to the chosen model, and to the AI coding assistants used to build this. A test (`tests/test_no_leak.py`) blocks `labels`/`notes` from reaching the pipeline. Extension only: generated months went to Anthropic, DeepSeek and Kimi models, and the fine-tuning ran on a rented GPU and a local Mac.
**Model and spend:** classifier `openai/gpt-oss-safeguard-20b` (OpenAI's policy-reasoning model: it classifies against written rules) through OpenRouter, $0.075 / $0.30 per million tokens in/out. A full run of the 32 receipts costs $0.0064 (0 failures); the four-model comparison (`output/compare/`) cost $0.0304 in total. OpenRouter key usage for this work so far: $0.037 *(final figure to be updated; it must match the OpenRouter dashboard)*.

## One receipt end to end
RCP-014 (supermarket, 4 lines): the classifier returns `household_goods` for detergent, paper towels and dish soap and `alcohol` (restricted, `high`) for "Cooking wine - Marsala 375ml" → the retriever selects the household, alcohol and merchant rules → the engine fires **ALC-03** on L4 (alcohol from a non-restaurant is never reimbursable), **HOUSE-01** on L1–L3 and **DOC-03**, plus the review signal **MCC-02** (MCC 5411, medium risk, not an exception) → EXC-01 gives `flag` → the reporter quotes the policy sentence for each finding with its line ids.

## AWS
`AWS_DESIGN.md`: async API Gateway + SQS + Lambda, policy bundle versioned in S3 (a policy change is a code change, shipped with tests), key in Secrets Manager, ~$630–930/month at 50,000 receipts/day.

## Known limits and next steps
Thresholds use the recorded USD amount with a 1% tolerance, so a wrong conversion can pass; a malformed field disables its rule family and the verdict falls to `review`; gift recipients are matched by the model's exact name text; TIME-04 cannot be measured because trip records carry nights but no dates; a model outage aborts the CLI. Next: validate recorded USD against the receipt's own rate, normalise MCC and entity inputs, calibrate confidence and EXC-03 on a labelled random sample at a realistic violation rate, and keep the pattern reviewer only if it beats a frontier comparator on a blind exam.

## AI collaboration
I used AI assistants as a tool to build and check the work; the design and the judgment about the data are mine. Full account in `AI_LOG.md`.
- **Direction and data judgment (mine).** I specified the architecture (a deterministic engine owns the verdict; a second-line reviewer reads a whole month and can only escalate `pass → review`), proposed fine-tuning a small local model for cross-receipt fraud and generating synthetic fraud histories that the engine classifies as `pass`, added red-team agents to remove my own bias as author, asked for data from several model families because one family shares blind spots, insisted on an exam independent of the training generator, and asked for a blind audit of the synthetic labels.
- **What the assistant did.** Code, experiment runs, drafts and audits.
- **What it got wrong, and how it was caught.** Training data with a weekend shortcut (counterfactual experiment); Opus 4.5 API results that did not represent the model (a rejected request parameter); a README line saying "temperature 0" that the code contradicted and an AWS cost taken from an older run (final audit); viewer rendering bugs (screenshots).
- **What I checked.** Answer key out of the pipeline with a leak test; a baseline frozen by hash; success criteria written before results; five independent audits, one recomputing every metric from the raw files.
