from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any


class OpenAIEmbeddingProvider:
    """Minimal auditable OpenAI embeddings client with usage telemetry."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120,
        cost_per_million_tokens: float = 0.02,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cost_per_million_tokens = cost_per_million_tokens
        self.calls = 0
        self.input_items = 0
        self.input_tokens = 0
        self.latency_ms = 0.0

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        started = time.perf_counter()
        request = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=json.dumps({"model": self.model, "input": texts}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload: dict[str, Any] = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"embedding provider HTTP {exc.code}: {detail[:500]}") from exc
        finally:
            self.latency_ms += (time.perf_counter() - started) * 1000
        rows = sorted(payload.get("data", []), key=lambda row: int(row.get("index", 0)))
        vectors = [row.get("embedding", []) for row in rows]
        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            raise RuntimeError("embedding provider returned missing or misaligned vectors")
        self.calls += 1
        self.input_items += len(texts)
        self.input_tokens += int(payload.get("usage", {}).get("total_tokens", 0))
        return vectors

    def telemetry(self) -> dict[str, Any]:
        return {
            "embedding_model": self.model,
            "embedding_calls": self.calls,
            "embedding_input_items": self.input_items,
            "embedding_input_tokens": self.input_tokens,
            "embedding_latency_ms": self.latency_ms,
            "estimated_embedding_cost_usd": (
                self.input_tokens * self.cost_per_million_tokens / 1_000_000
            ),
        }
