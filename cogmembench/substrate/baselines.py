from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import replace
from typing import Any, Protocol

from .adapter import (
    CapabilityManifest,
    ClockMode,
    EvidenceMode,
    RetrievalBudget,
    RetrievalRepresentation,
    RetrievalResult,
    RetrievedArtifact,
    UsageFidelity,
    UsageReport,
)
from .flat import FlatSubstrateAdapter, _terms, bm25_scores
from .schema import (
    ArtifactKind,
    CognitiveArtifact,
    EpistemicStatus,
    TimeInterval,
    Visibility,
)


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def telemetry(self) -> dict[str, Any]: ...


class DeterministicHashEmbeddingProvider:
    """Credential-free feature-hashing vectors for contract and CI runs only."""

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions
        self.calls = 0
        self.input_items = 0
        self.input_tokens = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            terms = _terms(text)
            vector = [0.0] * self.dimensions
            for term in terms:
                digest = hashlib.sha256(term.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append([value / norm for value in vector] if norm else vector)
            self.input_tokens += len(terms)
        if texts:
            self.calls += 1
            self.input_items += len(texts)
        return vectors

    def telemetry(self) -> dict[str, Any]:
        return {
            "embedding_provider": "deterministic-feature-hash",
            "embedding_model": "sha256-token-hash-v1",
            "embedding_dimensions": self.dimensions,
            "embedding_calls": self.calls,
            "embedding_input_items": self.input_items,
            "embedding_input_tokens": self.input_tokens,
            "estimated_embedding_cost_usd": 0.0,
            "scientific_evidence": False,
        }


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


class VectorSubstrateAdapter(FlatSubstrateAdapter):
    """Standalone dense-vector retrieval over the shared canonical rendering."""

    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        super().__init__()
        self.embedding_provider = embedding_provider
        self._vectors: dict[str, dict[str, list[float]]] = {}

    @property
    def _namespace_vectors(self) -> dict[str, list[float]]:
        if self._namespace is None:
            _ = self._state
        return self._vectors[self._namespace or ""]

    def reset(self, namespace: str) -> None:
        super().reset(namespace)
        self._vectors[namespace] = {}

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.embedding_provider.embed(texts)
        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            raise RuntimeError("embedding provider returned missing or misaligned vectors")
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) > 1:
            raise RuntimeError("embedding provider returned inconsistent dimensions")
        return vectors

    def commit(self, artifact: CognitiveArtifact, logical_time: int) -> CognitiveArtifact:
        stored = super().commit(artifact, logical_time)
        if stored.artifact_id not in self._namespace_vectors:
            self._namespace_vectors[stored.artifact_id] = self._embed(
                [self._retrieval_text(stored)]
            )[0]
        return stored

    def retrieve(
        self,
        query: str,
        budget: RetrievalBudget,
        logical_time: int,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> RetrievalResult:
        self._advance(logical_time)
        artifacts = self._visible_artifacts(valid_at, known_at)
        if not artifacts:
            return self._bounded_result(query, [], budget, logical_time)
        query_vector = self._embed([query])[0]
        ranked = sorted(
            (
                (_cosine(query_vector, self._namespace_vectors[row.artifact_id]), row)
                for row in artifacts
            ),
            key=lambda pair: (-pair[0], pair[1].artifact_id),
        )
        scored = [
            RetrievedArtifact(
                artifact,
                score,
                {"mode": "vector", "rank": rank, "cosine_score": score},
            )
            for rank, (score, artifact) in enumerate(ranked, start=1)
        ]
        return self._bounded_result(query, scored, budget, logical_time)

    def usage_report(self) -> UsageReport:
        base = super().usage_report()
        telemetry = self.embedding_provider.telemetry()
        vector_bytes = len(
            json.dumps(self._namespace_vectors, sort_keys=True, separators=(",", ":")).encode()
        )
        return replace(
            base,
            embedding_calls=int(telemetry.get("embedding_calls", 0)),
            storage_bytes=(base.storage_bytes or 0) + vector_bytes,
            metadata={**base.metadata, "embedding": telemetry},
        )

    def capability_manifest(self) -> CapabilityManifest:
        telemetry = self.embedding_provider.telemetry()
        provider = telemetry.get("embedding_provider", "configured")
        model = telemetry.get("embedding_model", "unknown")
        return CapabilityManifest(
            adapter_name="flat-vector",
            adapter_version="2.0.0",
            clock_mode=ClockMode.NATIVE,
            snapshot=True,
            branching=False,
            audit_export=False,
            agent_directed_capture=True,
            oracle_capture=True,
            usage_fidelity=UsageFidelity.COMPLETE,
            asynchronous_ingestion=False,
            notes=(
                "vectors index the fixed canonical artifact rendering",
                f"embedding_provider={provider}; embedding_model={model}",
                "relations are retained as evaluator-visible metadata, not used for ranking",
            ),
            evidence_mode=EvidenceMode.MAPPED,
            retrieval_representation=RetrievalRepresentation.CANONICAL,
        )


class HybridSubstrateAdapter(VectorSubstrateAdapter):
    """BM25/vector reciprocal-rank fusion over identical canonical documents."""

    def __init__(self, embedding_provider: EmbeddingProvider, *, rrf_k: int = 60) -> None:
        if rrf_k <= 0:
            raise ValueError("rrf_k must be positive")
        super().__init__(embedding_provider)
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        budget: RetrievalBudget,
        logical_time: int,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> RetrievalResult:
        self._advance(logical_time)
        artifacts = self._visible_artifacts(valid_at, known_at)
        if not artifacts:
            return self._bounded_result(query, [], budget, logical_time)
        documents = [self._retrieval_text(row) for row in artifacts]
        lexical_scores = bm25_scores(query, documents)
        lexical_order = sorted(
            (
                (score, artifact.artifact_id)
                for score, artifact in zip(lexical_scores, artifacts)
                if score > 0
            ),
            key=lambda pair: (-pair[0], pair[1]),
        )
        lexical_ranks = {
            artifact_id: rank
            for rank, (_, artifact_id) in enumerate(lexical_order, start=1)
        }
        lexical_by_id = {
            artifact.artifact_id: score
            for artifact, score in zip(artifacts, lexical_scores)
        }

        query_vector = self._embed([query])[0]
        semantic_scores = {
            artifact.artifact_id: _cosine(
                query_vector,
                self._namespace_vectors[artifact.artifact_id],
            )
            for artifact in artifacts
        }
        semantic_order = sorted(
            artifacts,
            key=lambda row: (-semantic_scores[row.artifact_id], row.artifact_id),
        )
        semantic_ranks = {
            artifact.artifact_id: rank
            for rank, artifact in enumerate(semantic_order, start=1)
        }

        scored: list[RetrievedArtifact] = []
        for artifact in artifacts:
            lexical_rank = lexical_ranks.get(artifact.artifact_id)
            semantic_rank = semantic_ranks[artifact.artifact_id]
            score = 1 / (self.rrf_k + semantic_rank)
            legs: dict[str, Any] = {
                "vector": {
                    "rank": semantic_rank,
                    "cosine_score": semantic_scores[artifact.artifact_id],
                }
            }
            if lexical_rank is not None:
                score += 1 / (self.rrf_k + lexical_rank)
                legs["bm25"] = {
                    "rank": lexical_rank,
                    "raw_score": lexical_by_id[artifact.artifact_id],
                }
            scored.append(
                RetrievedArtifact(
                    artifact,
                    score,
                    {"mode": "hybrid", "rrf_k": self.rrf_k, "legs": legs},
                )
            )
        scored.sort(key=lambda item: (-item.score, item.artifact.artifact_id))
        scored = [
            replace(item, metadata={**item.metadata, "rank": rank})
            for rank, item in enumerate(scored, start=1)
        ]
        return self._bounded_result(query, scored, budget, logical_time)

    def capability_manifest(self) -> CapabilityManifest:
        vector = super().capability_manifest()
        return replace(
            vector,
            adapter_name="flat-hybrid",
            notes=(
                *vector.notes,
                f"fusion=reciprocal-rank-fusion; rrf_k={self.rrf_k}",
            ),
        )


def _truncate_words(text: str, limit: int) -> str:
    matches = list(re.finditer(r"[a-z0-9]+", text, re.I))
    if len(matches) <= limit:
        return text
    return text[: matches[limit - 1].end()].rstrip() + " …"


class SummarySubstrateAdapter(FlatSubstrateAdapter):
    """Deterministic rolling extractive summary baseline."""

    def __init__(self, *, summary_tokens: int = 600) -> None:
        if summary_tokens <= 0:
            raise ValueError("summary_tokens must be positive")
        super().__init__()
        self.summary_tokens = summary_tokens

    def _retrieval_text(self, artifact: CognitiveArtifact) -> str:
        if artifact.structured_content.get("summary_source_ids") is not None:
            return artifact.content
        return super()._retrieval_text(artifact)

    def retrieve(
        self,
        query: str,
        budget: RetrievalBudget,
        logical_time: int,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> RetrievalResult:
        self._advance(logical_time)
        artifacts = self._visible_artifacts(valid_at, known_at)
        if not artifacts:
            return self._bounded_result(query, [], budget, logical_time)
        token_limit = min(
            self.summary_tokens,
            budget.max_context_tokens or self.summary_tokens,
        )
        newest_first = sorted(
            artifacts,
            key=lambda row: (
                -(row.transaction_time.start if row.transaction_time else 0),
                row.artifact_id,
            ),
        )
        selected: list[tuple[CognitiveArtifact, str]] = []
        used = 0
        for artifact in newest_first:
            line = (
                f"[{artifact.kind.value}; valid={artifact.valid_time.start}:"
                f"{'open' if artifact.valid_time.end is None else artifact.valid_time.end}; "
                f"status={artifact.epistemic_status.value}] {artifact.content}"
            )
            line_tokens = len(_terms(line))
            remaining = token_limit - used
            if remaining <= 0:
                break
            if line_tokens > remaining:
                line = _truncate_words(line, remaining)
                line_tokens = len(_terms(line))
            selected.append((artifact, line))
            used += line_tokens
        selected.reverse()
        source_ids = tuple(row.artifact_id for row, _ in selected)
        content = "Rolling memory summary:\n" + "\n".join(line for _, line in selected)
        digest = hashlib.sha256(
            f"{self._namespace}\0{logical_time}\0{source_ids}\0{content}".encode()
        ).hexdigest()[:16]
        summary = CognitiveArtifact(
            artifact_id=f"summary:{digest}",
            kind=ArtifactKind.CONCLUSION,
            content=content,
            scenario_id=self._namespace or "",
            valid_time=TimeInterval(valid_at or 0),
            transaction_time=TimeInterval(logical_time),
            structured_content={"summary_source_ids": source_ids},
            epistemic_status=EpistemicStatus.ACCEPTED,
            visibility=Visibility.AGENT,
        )
        result = RetrievedArtifact(
            summary,
            1.0,
            {
                "mode": "rolling-extractive-summary",
                "rank": 1,
                "source_artifact_ids": source_ids,
                "summary_tokens": used,
            },
        )
        return self._bounded_result(query, [result], budget, logical_time)

    def capability_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            adapter_name="rolling-summary",
            adapter_version="2.0.0",
            clock_mode=ClockMode.NATIVE,
            snapshot=True,
            branching=False,
            audit_export=False,
            agent_directed_capture=True,
            oracle_capture=True,
            usage_fidelity=UsageFidelity.COMPLETE,
            asynchronous_ingestion=False,
            max_context_items=1,
            notes=(
                f"deterministic rolling extractive summary; max_tokens={self.summary_tokens}",
                "source artifacts are retained for temporal filtering and conformance",
                "relations are retained as evaluator-visible metadata, not used for summarization",
            ),
            evidence_mode=EvidenceMode.MAPPED,
            retrieval_representation=RetrievalRepresentation.SUMMARY,
        )
