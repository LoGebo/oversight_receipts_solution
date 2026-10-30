"""OpenRouter path of the classifier through httpx.MockTransport: no network, no real key."""
import json
import logging

import httpx
import pytest

from validator import classifier
from validator.classifier import SCHEMA, SYSTEM, classify
from conftest import RECEIPTS, line, reply

KEY = "sk-or-v1-TEST-SECRET-0123456789"
MODEL = classifier.OPENROUTER_MODEL
GOOD = reply(line("RCP-009-L1", "laundry_service"))


def endpoints(*params_per_endpoint):
    return {"data": {"endpoints": [{"supported_parameters": list(p), "pricing": {
        "prompt": "0.0000001", "completion": "0.0000005", "overrides": [{"prompt": "0.0000005", "completion": "0.0000025"}]}}
        for p in params_per_endpoint]}}


HAIKU = endpoints(["structured_outputs", "response_format", "reasoning", "max_tokens"])  # as listed for Haiku 5.5


def chat(content=GOOD, finish="stop", cost=0.00123, refusal=None):
    return {"id": "gen-1", "model": MODEL, "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "cost": cost},
            "choices": [{"finish_reason": finish, "message": {"role": "assistant", "content": content, "refusal": refusal}}]}


class OR:
    """An httpx.Client on a MockTransport: the endpoint list, then chat replies in order (an Exception is raised)."""

    def __init__(self, *replies, eps=HAIKU):
        self.replies, self.requests, self.eps = list(replies), [], eps
        self.client = httpx.Client(base_url=classifier.OPENROUTER_URL, transport=httpx.MockTransport(self.handle),
                                   headers={"Authorization": f"Bearer {KEY}"})

    def handle(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        if req.method == "GET":
            return httpx.Response(200, json=self.eps)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)

    @property
    def posts(self):
        return [json.loads(q.content) for q in self.requests if q.method == "POST"]


def run(rid, fake, tmp_path, **kw):
    return classify([RECEIPTS[rid]], provider="openrouter", client=fake.client, cache_dir=tmp_path, **kw)


def test_request_shape_and_parsing_with_reported_cost(tmp_path):
    fake = OR(chat())
    c = run("RCP-009", fake, tmp_path)
    get, post = fake.requests
    assert str(get.url) == f"https://openrouter.ai/api/v1/models/{MODEL}/endpoints"
    assert str(post.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert post.headers["authorization"] == f"Bearer {KEY}"
    (body,) = fake.posts
    assert body["model"] == MODEL and body["max_tokens"] == classifier.MAX_TOKENS
    assert body["response_format"] == {"type": "json_schema",
                                       "json_schema": {"name": "receipt_lines", "strict": True, "schema": SCHEMA}}
    assert body["provider"] == {"require_parameters": True}
    assert body["messages"][0] == {"role": "system", "content": SYSTEM} and body["messages"][1]["role"] == "user"
    assert "temperature" not in body and body["reasoning"] == {"effort": classifier.EFFORT}  # Haiku 5.5 takes no temperature
    assert c.categories == {"RCP-009-L1": "laundry_service"} and not c.meta["failures"]
    assert c.meta["cost_usd"] == 0.00123 and c.meta["provider"] == "openrouter" and c.meta["model"] == MODEL
    assert (c.meta["input_tokens"], c.meta["output_tokens"]) == (1000, 200)


def test_temperature_zero_when_every_structured_endpoint_takes_it(tmp_path):
    fake = OR(chat(), eps=endpoints(["structured_outputs", "temperature"], ["structured_outputs", "temperature", "reasoning"],
                                    ["temperature"]))  # the last one has no structured outputs: ignored
    run("RCP-009", fake, tmp_path)
    (body,) = fake.posts
    assert body["temperature"] == 0 and "reasoning" not in body


def test_model_without_structured_outputs_is_a_clear_failure_without_a_chat_call(tmp_path):
    fake = OR(eps=endpoints(["temperature", "response_format"]))
    c = run("RCP-009", fake, tmp_path)
    assert fake.posts == [] and "no OpenRouter endpoint with structured outputs" in c.meta["failures"]["RCP-009"]
    assert c.categories == {"RCP-009-L1": "other"} and c.uncertain == {"RCP-009": {"RCP-009-L1"}}


BAD = [
    chat("not json"),
    chat(None),
    chat(reply(line("RCP-002-L1"))),                                         # lines missing
    chat("", refusal="I can't help with that"),
    chat(reply(line("RCP-002-L1"), line("RCP-002-L2"), line("RCP-002-L3")), finish="length"),
    chat(finish="content_filter"),
    {"error": {"code": 502, "message": "provider error"}},                   # error with HTTP 200
    {"usage": {"prompt_tokens": 1, "completion_tokens": 1}, "choices": []},  # no cost, no choice
    httpx.Response(400, json={"error": {"code": 400, "message": "bad request"}}),  # not transient: no backoff
]
TRANSIENT = [httpx.Response(429, json={"error": {"code": 429, "message": "rate limited"}}), httpx.Response(500, text="boom"),
             httpx.Response(503, text="busy"), httpx.ReadTimeout("timed out")]


@pytest.mark.parametrize("bad", BAD)
def test_fails_closed_after_one_retry(tmp_path, bad, caplog):
    caplog.set_level(logging.DEBUG)
    fake = OR(bad, bad)
    c = run("RCP-002", fake, tmp_path)
    assert len(fake.posts) == 2 and "RCP-002" in c.meta["failures"]
    assert set(c.categories.values()) == {"other"} and c.uncertain == {"RCP-002": {"RCP-002-L1", "RCP-002-L2", "RCP-002-L3"}}
    assert KEY not in json.dumps(c.meta, default=str) and KEY not in caplog.text
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("bad", TRANSIENT)
def test_transient_errors_back_off_three_attempts_then_fail_closed(tmp_path, bad, sleeps):
    fake = OR(*[bad] * 6)
    c = run("RCP-002", fake, tmp_path)
    assert len(fake.posts) == 6 and "RCP-002" in c.meta["failures"] and c.meta["calls"] == 2
    assert sleeps == [1.0, 2.0, classifier.RETRY_PAUSE, 1.0, 2.0]  # 3 attempts per call, one call retried once
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("header, wait", [("7", 7.0), ("3600", classifier.HTTP_MAX_WAIT), ("0", 0.0),
                                          ("Wed, 21 Oct 2026 07:28:00 GMT", 1.0)])  # a date: plain backoff
def test_retry_after_is_honoured_and_capped(tmp_path, sleeps, header, wait):
    fake = OR(httpx.Response(429, headers={"Retry-After": header}), chat())
    c = run("RCP-009", fake, tmp_path)
    assert len(fake.posts) == 2 and sleeps == [wait] and c.categories == {"RCP-009-L1": "laundry_service"}


def test_transient_error_on_the_endpoint_list_is_retried(tmp_path, sleeps):
    eps = iter([httpx.Response(502), httpx.Response(200, json=HAIKU)])
    fake = OR(chat())
    fake.handle = lambda req, real=fake.handle: next(eps) if req.method == "GET" else real(req)
    fake.client = httpx.Client(base_url=classifier.OPENROUTER_URL, transport=httpx.MockTransport(fake.handle))
    assert run("RCP-009", fake, tmp_path).categories == {"RCP-009-L1": "laundry_service"} and sleeps == [1.0]


def test_retry_recovers_and_spend_sums_reported_costs(tmp_path):
    fake = OR(chat("garbage", cost=0.001), chat(cost=0.002))
    c = run("RCP-009", fake, tmp_path)
    assert len(fake.posts) == 2 and c.categories == {"RCP-009-L1": "laundry_service"}
    assert c.meta["cost_usd"] == pytest.approx(0.003)


def test_cache_entry_records_provider_and_model_and_key_differs_by_provider(tmp_path):
    run("RCP-009", OR(chat()), tmp_path)
    (path,) = tmp_path.iterdir()
    entry = json.loads(path.read_text(encoding="utf-8"))
    assert (entry["provider"], entry["model"]) == ("openrouter", MODEL) and KEY not in path.read_text(encoding="utf-8")
    assert entry["response_id"] == "gen-1" and entry["usage"] == {"input_tokens": 1000, "output_tokens": 200, "cost_usd": 0.00123}
    assert entry["created_utc"].endswith("+00:00")
    again = OR()
    assert run("RCP-009", again, tmp_path).meta["cache_hits"] == 1 and again.requests == []  # warm: no network at all
    payload = "{}"
    keys = {classifier.cache_key(MODEL, payload, "openrouter"), classifier.cache_key(MODEL, payload, "anthropic")}
    assert len(keys) == 2
    assert classifier.cache_key(MODEL, payload) == classifier.cache_key(MODEL, payload, "openrouter")  # committed cache key


def test_spend_guard_uses_endpoint_prices_and_stops_calls(tmp_path):
    batch = [RECEIPTS["RCP-009"], RECEIPTS["RCP-031"]]
    fake = OR(chat(cost=0.01))
    # worst case per call at the dearest listed price ($0.5/$2.5 per MTok): ~$0.016; after $0.01 spent, no room
    c = classify(batch, provider="openrouter", client=fake.client, cache_dir=tmp_path, budget_usd=0.02)
    assert len(fake.posts) == 1 and "budget" in c.meta["failures"]["RCP-031"] and c.meta["cost_usd"] == 0.01


def test_default_client_sends_the_key_from_the_environment_only_in_the_header(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    client = classifier._client("openrouter")
    assert client.headers["authorization"] == f"Bearer {KEY}" and str(client.base_url) == "https://openrouter.ai/api/v1/"
    assert KEY not in repr(client)


@pytest.mark.parametrize("env, want", [({"OPENROUTER_API_KEY": "x"}, "openrouter"), ({"ANTHROPIC_API_KEY": "x"}, "anthropic"),
                                       ({"OPENROUTER_API_KEY": "x", "ANTHROPIC_API_KEY": "y"}, "openrouter"), ({}, "openrouter")])
def test_default_provider(monkeypatch, env, want):
    for k in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert classifier.default_provider() == want
