from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .base import ProviderResponse, ToolCall


class OpenAICompatibleProvider:
    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        timeout: float = 90,
        *,
        provider_preferences: dict[str, Any] | None = None,
        disable_reasoning: bool = False,
        omit_temperature: bool = False,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
    ):
        self.model_id = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.provider_preferences = provider_preferences
        self.disable_reasoning = disable_reasoning
        self.omit_temperature = omit_temperature
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0,
        max_output_tokens: int = 1024,
    ) -> ProviderResponse:
        body: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_output_tokens,
        }
        if not self.omit_temperature:
            body["temperature"] = temperature
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if self.provider_preferences:
            body["provider"] = self.provider_preferences
        if self.disable_reasoning:
            body["reasoning"] = {"enabled": False, "exclude": True}
        endpoint = (
            f"{self.base_url}/chat/completions"
            if self.base_url.endswith("/v1")
            else f"{self.base_url}/v1/chat/completions"
        )
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        attempts = 0
        while True:
            attempts += 1
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read())
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")
                retryable = exc.code == 429 or 500 <= exc.code < 600
                if not retryable or attempts > self.max_retries:
                    raise RuntimeError(
                        f"provider HTTP {exc.code} after {attempts} attempt(s): {detail[:500]}"
                    ) from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = float(retry_after) if retry_after else 0.0
                except ValueError:
                    delay = 0.0
                time.sleep(max(delay, self.retry_backoff_seconds * (2 ** (attempts - 1))))
        message = data["choices"][0]["message"]
        calls = []
        for call in message.get("tool_calls", []):
            raw_args = call.get("function", {}).get("arguments", "{}")
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {"_malformed": raw_args}
            calls.append(ToolCall(call.get("id", ""), call["function"]["name"], args))
        usage = data.get("usage", {})
        detail = usage.get("completion_tokens_details", {}) or {}
        return ProviderResponse(
            content=message.get("content") or "",
            tool_calls=calls,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            reasoning_tokens=detail.get("reasoning_tokens"),
            cost_usd=usage.get("cost"),
            model=data.get("model", self.model_id),
            raw={"id": data.get("id"), "usage": usage, "attempts": attempts},
        )
