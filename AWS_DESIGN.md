# AWS deployment design (on paper)

Not deployed. List prices, us-east-1, checked 2026-10-26 unless *unverified*.

```
client ─JWT─▶ API Gateway (HTTP API) ─▶ intake Lambda ─▶ SQS ─▶ worker Lambda ─▶ S3 report + DynamoDB index
                                                      │ DLQ     normalise → classify (1 LLM call) → retrieve → engine → report
                                                      ▼         reads: Secrets Manager (key), S3 policy bundle; logs: CloudWatch
                                                  alarm
```

**Architecture.** Async: `POST /receipts` returns `202`, SQS absorbs peaks, `GET /receipts/{id}` returns the report. The worker runs the pipeline as a library; only the classifier leaves the process. Cross-receipt rules (MEAL-01, REG-03 per employee-day; medication per trip) re-run on stored classified lines, limited to one employee-day or trip per receipt, rules only. A late receipt can change an earlier verdict (new report version). Reads are bounded (in the 2 per receipt below).

**Policy documents.** The 9 files are one bundle in a versioned S3 bucket with a sha256 manifest, and the worker refuses to run on a checksum mismatch. Caps and thresholds are encoded in the rule modules (`rules/*.py`), not read from the text, so a policy change is a code change: update the encoded rule and its tests, run CI, publish a new bundle and worker version together, then roll out. Hot-reloading only the documents would leave the quoted text and the enforced number out of step. Each report carries a `policy_version` field.

**Auth and secrets.** Cognito federated to company SSO, checked by a JWT authorizer. `tenant_id` comes from the token and prefixes every key, enforced by IAM conditions. The model key lives in Secrets Manager (KMS, rotated), never in code, `.env`, images or Lambda environment variables. Provider: the Anthropic API as measured here, or Bedrock, which needs no key.

**Personal data.** This exercise sent receipts to the Anthropic API (`claude-haiku-5-5`) and to coding assistants. Receipts carry names, so an external provider needs a DPA and retention terms. Whether Bedrock offers Haiku 5.5, and at what price, is *unverified*.

**Failures.** A model error, timeout or invalid output after one retry gives `review`, never `pass`. After 3 failures a message goes to a DLQ with an alarm. A circuit breaker stops model calls when over 10% fail in one minute, returning `review` until a probe succeeds. `receipt_id` is the idempotency key.

**Cost at 50,000 receipts/day (1.5M/month).** Held-out run with the final prompt v3 (`data_heldout/run_record.json`): 119,343 in / 19,195 out tokens over 41 receipts = 2,911 + 468 per receipt. At Haiku 5.5 list ($0.10/$0.50 per MTok, Anthropic, 2026-10-06): 2,911 × $0.10/M + 468 × $0.50/M = **$0.000525/receipt**. Low end, dataset run (90,762 in / 6,555 out over 32 receipts): $0.012354 / 32 = $0.000386.

| Item | Working (per month) | $/month |
|---|---|---|
| Model calls | 1.5M × $0.000386–0.000525 | 579–788 |
| Worker Lambda | 1.5M × 0.5 GB × 3–10 s *(assumed, mostly waiting on the model)* × $0.0000166667 + $0.30 requests | 38–125 |
| API Gateway, SQS | 1.5M × $1.00/M; 3 req × 1.5M × $0.40/M | 3.30 |
| DynamoDB on-demand | ~3 writes × $0.625/M + 2 reads × $0.125/M per receipt | 3.20 |
| S3, Logs, Secrets *(unverified)* | 1.5M PUT × $0.005/1k; ~3 GB logs × $0.50; 1 secret × $0.40 | ~9.50 |
| **Total** | **$0.0004–0.0006 per receipt** | **~630–930** |

The model is 84–92% of cost. The Batch API halves it if reports can wait. Caching the ~2,500-token fixed prompt (derived, not measured) at 0.1× would save ~$340/month; stacking is unchecked. Sonnet 5.5 at $2/$10 is ~$15,400/month (20× the Haiku price per token).

**Before production.**
1. Calibrate confidence and the EXC-03 threshold on a labelled random sample of real receipts (dataset: all 79 lines high or rule-set; held-out: 5 of 144 low), plus retriever recall and per-rule precision at a real violation rate.
2. Data protection: a DPA, lifecycle expiry for stored data, and dropping unneeded names before the model call.
3. Load-test at 5–10× the 0.6/s average against provider rate limits, and force an outage to confirm only `review` and alarms.
