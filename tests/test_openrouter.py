from __future__ import annotations

import json
import urllib.error

from cogmembench.providers import OpenAICompatibleProvider


def test_openrouter_request_is_pinned_and_does_not_duplicate_v1(monkeypatch):
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                {
                    "id": "generation-1",
                    "model": "qwen/qwen3-32b",
                    "choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "cost": 0.00001},
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider(
        "qwen/qwen3-32b",
        "https://openrouter.ai/api/v1",
        "test-key",
        provider_preferences={"only": ["deepinfra"], "allow_fallbacks": False},
        disable_reasoning=True,
    )
    response = provider.complete([{"role": "user", "content": "test"}])
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["body"]["provider"]["only"] == ["deepinfra"]
    assert captured["body"]["reasoning"]["enabled"] is False
    assert response.cost_usd == 0.00001


def test_temperature_can_be_omitted_for_models_that_reject_it(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                {
                    "choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data))
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider(
        "openai/gpt-5.4-mini",
        "https://openrouter.ai/api/v1",
        "test-key",
        omit_temperature=True,
    )
    provider.complete([{"role": "user", "content": "test"}], temperature=0)
    assert "temperature" not in captured


def test_transient_provider_error_is_retried_and_counted(monkeypatch):
    calls = 0

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                {
                    "id": "retry-success",
                    "choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            ).encode()

    def flaky_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url, 429, "rate limited", {}, None
            )
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", flaky_urlopen)
    monkeypatch.setattr("time.sleep", lambda _: None)
    provider = OpenAICompatibleProvider(
        "model",
        "https://openrouter.ai/api/v1",
        "test-key",
        max_retries=1,
    )
    response = provider.complete([{"role": "user", "content": "test"}])

    assert calls == 2
    assert response.raw["attempts"] == 2
    assert response.raw["id"] == "retry-success"
