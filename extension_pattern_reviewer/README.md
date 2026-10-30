# Extension: pattern reviewer (fine-tuning experiments)

This folder is an optional extension to the expense validator in the parent directory. It explores whether a small fine-tuned LLM can act as a "pattern reviewer": reading an employee's expense history and flagging multi-receipt fraud patterns that the deterministic engine does not catch. The design was inspired by an industry case study.

The core deliverable (engine, tests, viewer, outputs) lives in the parent folder and does not depend on anything here.

## Status

Work in progress. Results are mixed and partly negative or inconclusive; they are kept on purpose because the honest record is part of the deliverable. Read `docs/FINETUNE_LOG.md` (in Spanish, to be translated) for dated decisions and results, and `docs/REVISION_OPUS55.md` for the critical review.

## Map

| Folder | Contents |
|---|---|
| `docs/` | Decision log (`FINETUNE_LOG.md`), plan v2, critical review, findings of frauds the engine misses, handoff notes. |
| `../notebooks/extension_pattern_reviewer/` | Not in this folder: notebooks 00-03 and ANNEX 1-4 (saved with outputs), helpers (`design_helpers.py`, `evaluation.py`, `engine_api.py`), the `engine/` copy and `data/` they read live under the repo's top-level `notebooks/`. Start with `00_INDEX.ipynb`; see `../notebooks/README.md`. |
| `data_generation/` | v2 synthetic-history generation (`gen.py`, `skeleton.py`, `gate.py`, `claude_route.py`, `build_sft_v2.py`), the human-months template, and `pipeline/` (v1 data scripts, scoring, writer prompt). |
| `training/` | `modal_train.py` (Modal GPU training), SFT `train.jsonl`, `valid.jsonl`, `split.json`; `v1_sft/` for the first dataset. |
| `data/` | Validated synthetic histories from v2 generation (non-empty outputs only). |
| `results/` | Evaluation JSONs of baselines and fine-tuned runs, API runs, `modal_logs/`, `v2/`. |

## Caveats

- Notebooks 01-03 and ANNEX 2-4 were authored against a local layout (`~/finetune_project`, `/Users/.../finetune`); their saved outputs open fine, but re-running needs those paths adjusted and the large raw synthetic data (not included).
- Large raw synthetic datasets and temporary generation material were left out of this folder.
