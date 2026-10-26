# Decisions log

Each entry: what was decided, why, and who decided. The candidate decides; the assistant proposes and builds.

| # | Date | Decision | Why |
|---|---|---|---|
| D-001 | 2026-10-25 | The project lives outside the provided case folder; `data/` is a verbatim copy. | The provided folder is read-only material (see AGENTS.md one level up). |
| D-002 | 2026-10-25 | Answer keys are physically split from the input: `data_split/receipts_input.jsonl` (pipeline) and `data_split/gold.jsonl` (evaluation only), enforced by `tests/test_no_leak.py`. | The data README forbids using `labels`/`notes` as input or in prompts. A test is a stronger claim than a promise. |
| D-003 | 2026-10-25 | All 32 receipts are processed (group rules need same-day/same-trip context); only 28 are scored. RCP-020, 021, 029, 030 are excluded from scoring. | Brief section 2: TIME-01..04 are optional, their four receipts are not scored. |
| D-004 | 2026-10-25 | Python + uv + pytest. Dependencies are added when first needed, not up front. | Smallest working setup. |
| D-005 | 2026-10-25 | One commit per phase. | Git history is part of the submission. |

## Open

- Does a `PA-` reference satisfy TECH-04, ENT-01 or PERS-01/02? (EXC-02 reading: no, only the kind each rule asks for.)
- EXC-03 confidence threshold (must be stated in the README; every EXC-03 signal counts as unmatched).
- Primary classifier model (to be fixed before looking at the 28 results).
- Fine-tuning experiment: only if the engine passes its tests on Monday night.
