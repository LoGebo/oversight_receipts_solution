# Notebooks

Read in this order. Solution notebooks first, then the fine-tuning extension.

## Solution (top level, run from this folder)
1. `explorar.ipynb` - explore the receipts and policies data interactively (Spanish).
2. `entender_solucion.ipynb` - walk through the validator pipeline piece by piece to defend each decision (Spanish).

## Extension: pattern reviewer (`extension_pattern_reviewer/`, saved with outputs, English)
3. `00_INDEX.ipynb` - overview and guide to the rest.
4. `01_FINAL_full_story.ipynb` - the full story of the fine-tuning extension and its results.
5. `02_deterministic_engine.ipynb` - the deterministic engine (copy in `engine/`) and what it misses.
6. `03_finetuning_runs.ipynb` - fine-tuning runs, evaluation and how to reproduce.
7. `ANNEX_1_hardware_smoke_test.ipynb` - local hardware smoke test.
8. `ANNEX_2_synthetic_dataset_classifier.ipynb` - synthetic dataset for the classifier.
9. `ANNEX_3_baselines_classifier.ipynb` - baselines for the classifier.
10. `ANNEX_4_working_notes_pattern_reviewer.ipynb` - working notes on the pattern reviewer.

Helpers next to them: `design_helpers.py`, `evaluation.py`, `engine_api.py`, `build_bundle.py`, `engine/`, `data/`. Context: `../extension_pattern_reviewer/README.md`.
Note: the extension notebooks open with their saved outputs; re-running 01-03 and ANNEX 2-4 needs the original local paths (see that README).
