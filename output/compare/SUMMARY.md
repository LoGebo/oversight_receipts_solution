# Model comparison (classifier only, same engine)

Receipts: receipts_input.jsonl (32; 28 scored). Total spend $0.0304 of $1.0 cap.

| model | disposition acc | FP of 9 pass | missed of 16 flag | line category acc | macro F1 | restricted F1 | spend USD | latency s | calls | failures |
|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-oss-safeguard-20b | 28/28 (100%) | 0/9 | 0/16 | 63/65 (97%) | 0.963 | 0.976 | 0.0061 | 26.71 | 32 | 0 |
| anthropic/claude-haiku-5.5 | 28/28 (100%) | 0/9 | 0/16 | 65/65 (100%) | 1.000 | 1.000 | 0.0124 | 58.53 | 32 | 0 |
| openai/gpt-6-luna | 28/28 (100%) | 0/9 | 0/16 | 65/65 (100%) | 1.000 | 1.000 | 0.0035 | 62.03 | 32 | 0 |
| deepseek/deepseek-v4.1-flash | 28/28 (100%) | 0/9 | 0/16 | 65/65 (100%) | 1.000 | 1.000 | 0.0084 | 36.75 | 32 | 0 |

## Caveats

- Single run per model (temperature 0 where accepted, otherwise the provider default): no variance estimate.
- Only 28 scored receipts (9 pass, 16 flag, 3 review); one receipt is 3.6 points of disposition accuracy.
- The engine was written with these answers in view, so differences between models isolate the classifier, but absolute numbers are optimistic and not a held-out estimate.
- A model that fails closed on a receipt is scored on its fail-closed fallback (all lines other, review).
- Spend is the usage.cost OpenRouter reports; latency is wall time of the whole classify call, cache misses only.
