# AWS deployment design (on paper)

Not deployed. List prices, us-east-1, checked 2026-10-26 unless *unverified*.

```
client ─JWT─▶ API Gateway (HTTP API) ─▶ intake Lambda ─▶ SQS ─▶ worker Lambda ─▶ S3 report + DynamoDB index
                                                      │ DLQ     normalise → classify (1 LLM call) → retrieve → engine → report
                                                      ▼         reads: Secrets Manager (key), S3 policy bundle; logs: CloudWatch
                                                  alarm
```

**Architecture.** The service is async: `POST /receipts` returns `202`, SQS absorbs peaks, and `GET /receipts/{id}` returns the report. The worker runs the existing pipeline as a library. Only the classifier leaves the process. Some rules span receipts (MEAL-01, REG-03 per employee-day; medication per trip), so the worker stores classified lines in DynamoDB under those keys and re-runs those rules for the group; a late receipt can change an earlier verdict, saved as a new report version. The re-run is rules only (no new model call: classified lines are stored) and is limited to one employee-day or one trip per receipt, so it adds a bounded number of DynamoDB reads (included in the 2 reads per receipt below).

**Policy documents.** The 9 files are one bundle in a versioned S3 bucket, with a sha256 manifest. The worker reads the manifest version at cold start and again every 5 minutes (one S3 `HEAD`), reloads when it changes, and refuses to run on a checksum mismatch, so a policy change reaches running workers without a redeploy. Rules quote and encode this text, so a policy change ships like code: tests in CI, then publish. Each report gets a new `policy_version` field; today it names only `policy_doc`.

**Auth and secrets.** Callers sign in with Cognito federated to company SSO, checked by a JWT authorizer. `tenant_id` comes from the token and prefixes every key and path; IAM conditions keep each tenant inside its prefix. Each Lambda has a least-privilege role. The model key lives in Secrets Manager (KMS, rotated), read at cold start, never in code, `.env`, images or Lambda environment variables. Pick one provider per deployment: the Anthropic API (key in Secrets Manager) as measured here, or Bedrock, which needs no key because IAM authorises it.

**Model access and personal data.** This exercise sent receipts to the Anthropic API (`claude-haiku-5-5`) and to coding assistants; OpenRouter, unused, would add a second processor. Receipts carry names, such as a government official on a gift. An external provider needs a DPA, retention terms and an inference region. Bedrock keeps traffic in AWS; whether it offers Haiku 5.5, and at what price, is *unverified*.

**Failures and observability.** As in the code, a model error, timeout or invalid output after one retry gives `review`, never `pass`. After 3 failures a message goes to a DLQ with an alarm. A circuit breaker in the worker stops calling the model when more than 10% of calls fail in one minute and returns `review` for every receipt until a probe call succeeds. `receipt_id` is the idempotency key, and classifier results are cached by a sha256 of model, prompt and content. Metrics per tenant: cost per receipt, fail-closed rate, DLQ depth, confidence-band mix (drift), and rules the retriever missed (the engine already raises on these).

**Cost at 50,000 receipts/day (1.5M/month).** Measured on the held-out v2 run (`data_heldout/run_record.json`): 113,070 in / 19,344 out tokens over 41 receipts = 2,758 + 472 per receipt. At Haiku 5.5 list ($0.10/$0.50 per MTok, Anthropic, 2026-10-06): 2,758 × $0.10/M + 472 × $0.50/M = **$0.000512/receipt**. Low end, dataset run: $0.0119 / 32 = $0.000372.

| Item | Working (per month) | $/month |
|---|---|---|
| Model calls | 1.5M × $0.000372–0.000512 | 558–768 |
| Worker Lambda | 1.5M × 0.5 GB × 3–10 s *(assumed, mostly waiting on the model)* × $0.0000166667 + $0.30 requests | 38–125 |
| API Gateway, SQS | 1.5M × $1.00/M; 3 req × 1.5M × $0.40/M | 3.30 |
| DynamoDB on-demand | ~3 writes × $0.625/M + 2 reads × $0.125/M per receipt | 3.20 |
| S3, Logs, Secrets *(unverified)* | 1.5M PUT × $0.005/1k; ~3 GB logs × $0.50; 1 secret × $0.40 | ~9.50 |
| **Total** | **$0.0004–0.0006 per receipt** | **~610–910** |

The model is 84–92% of cost. The Batch API halves it if reports can wait. Caching the ~2,500-token fixed prompt (derived, not measured) at 0.1× would save ~$340/month; whether the two discounts stack is unchecked. Cost goes up 10× with a bigger model (Sonnet 5.5 at $2/$10 is ~$15,400/month), with images (not measured), or with a retry storm.

**Before production.**
1. Calibrate confidence and set the EXC-03 threshold on a labelled random sample of real receipts. On the dataset all 79 lines came back high or rule-set; on held-out, 5 of 144 came back low. On the same sample, measure retriever recall and per-rule precision at a real violation rate (a few percent).
2. Data protection: a DPA, lifecycle expiry for receipts, reports and the cache, and dropping names the rules do not need before the model call.
3. Load-test at 5–10× the 0.6/s average against provider rate limits, and force an outage to show it yields only `review` and alarms.
