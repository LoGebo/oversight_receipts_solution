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

**Auth and secrets.** Cognito federated to company SSO, checked by a JWT authorizer. `tenant_id` comes from the token and prefixes every key, enforced by IAM conditions. The model key lives in Secrets Manager (KMS, rotated), never in code, `.env`, images or Lambda environment variables. Provider: OpenRouter (`openai/gpt-oss-safeguard-20b`) as measured here; the Anthropic API stays a configured option, and Bedrock would need no key.

**Personal data.** This exercise sent receipts to OpenRouter (`openai/gpt-oss-safeguard-20b`, served by Groq, the only endpoint OpenRouter listed for it on 2026-10-29), earlier to the Anthropic API (`claude-haiku-5-5`), and to coding assistants. Receipts carry names, so an external provider, and the provider OpenRouter routes to, needs a DPA and retention terms. Whether Bedrock offers gpt-oss-safeguard-20b, and at what price, is *unverified*.

**Failures.** A model error, timeout or invalid output after one retry gives `review`, never `pass`. After 3 failures a message goes to a DLQ with an alarm. A circuit breaker stops model calls when over 10% fail in one minute, returning `review` until a probe succeeds. `receipt_id` is the idempotency key.

**Cost at 50,000 receipts/day (1.5M/month).** Model `openai/gpt-oss-safeguard-20b` on OpenRouter at $0.075 in / $0.30 out per MTok (OpenRouter endpoint list, Groq, checked 2026-10-29). Held-out run, prompt v3 (`data_heldout/run_record.json`): 72,061 in / 33,256 out tokens over 41 receipts = 1,758 + 811 per receipt (output includes the model's reasoning tokens): 1,758 × $0.075/M + 811 × $0.30/M = **$0.000375/receipt**. Low end, dataset run (usage per call in the classifier cache: 54,378 in / 12,427 out over 32 receipts = 1,699 + 388): **$0.000244/receipt**. OpenRouter's reported `usage.cost` was lower than tokens × list price on both runs ($0.013394 / 41 = $0.000327; $0.006414 / 32 = $0.000200); the table uses list price, the higher figure.

| Item | Working (per month) | $/month |
|---|---|---|
| Model calls | 1.5M × $0.000244–0.000375 | 366–563 |
| Worker Lambda | 1.5M × 0.5 GB × 3–10 s *(assumed, mostly waiting on the model)* × $0.0000166667 + $0.30 requests | 38–125 |
| API Gateway, SQS | 1.5M × $1.00/M; 3 req × 1.5M × $0.40/M | 3.30 |
| DynamoDB on-demand | ~3 writes × $0.625/M + 2 reads × $0.125/M per receipt | 3.20 |
| S3, Logs, Secrets *(unverified)* | 1.5M PUT × $0.005/1k; ~3 GB logs × $0.50; 1 secret × $0.40 | ~9.50 |
| **Total** | **$0.0003–0.0005 per receipt** | **~420–700** |

The model is 80–87% of cost. A batch discount for this route is *unverified* (OpenRouter lists none). If the provider billed the ~1,500-token fixed prompt (derived: the smallest measured input is 1,619 tokens) as cached input at 0.1× (*unverified* for this model), that would save ~$150/month. The previous classifier, Haiku 5.5 at $0.10/$0.50 (Anthropic list, 2026-10-06), measured 2,911 + 468 tokens per held-out receipt (`data_heldout/run_record_prompt_v3_haiku.json`): ~$790/month for model calls. Sonnet 5.5 at $2/$10 on those Haiku token counts would be ~$15,750/month, 28–43× this model's model-call line (Sonnet's own token counts not measured).

**Before production.**
1. Calibrate confidence and the EXC-03 threshold on a labelled random sample of real receipts (dataset: all 79 lines high or rule-set; held-out: 2 of 144 low, and 13 of the 20 non-exact lines rated high), plus retriever recall and per-rule precision at a real violation rate.
2. Data protection: a DPA, lifecycle expiry for stored data, and dropping unneeded names before the model call.
3. Load-test at 5–10× the 0.6/s average against provider rate limits, and force an outage to confirm only `review` and alarms.
