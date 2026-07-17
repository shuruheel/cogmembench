from __future__ import annotations

import math
import re
from collections import Counter

from .adapter import (
    CapabilityManifest,
    ClockMode,
    EvidenceMode,
    RetrievalBudget,
    RetrievalRepresentation,
    RetrievalResult,
    RetrievedArtifact,
    UnsupportedCapabilityError,
    UsageFidelity,
)
from .reference import ReferenceSubstrateAdapter
from .rendering import render_canonical_artifact
from .schema import AuditReceipt, CognitiveArtifact

WORD = re.compile(r"[a-z0-9]+")


def _terms(text: str) -> list[str]:
    return WORD.findall(text.lower())


def bm25_scores(query: str, documents: list[str]) -> list[float]:
    """Auditable Okapi BM25 scores with fixed k1=1.5 and b=0.75."""
    if not documents:
        return []
    tokenized = [_terms(document) for document in documents]
    query_terms = set(_terms(query))
    average_length = sum(len(document) for document in tokenized) / len(tokenized) or 1.0
    document_frequency = {
        term: sum(term in document for document in tokenized) for term in query_terms
    }
    scores: list[float] = []
    for document in tokenized:
        counts = Counter(document)
        score = 0.0
        for term in query_terms:
            frequency = counts[term]
            if not frequency:
                continue
            frequency_in_documents = document_frequency[term]
            inverse_document_frequency = math.log(
                1 + (len(tokenized) - frequency_in_documents + 0.5)
                / (frequency_in_documents + 0.5)
            )
            denominator = frequency + 1.5 * (
                1 - 0.75 + 0.75 * len(document) / average_length
            )
            score += inverse_document_frequency * frequency * 2.5 / denominator
        scores.append(score)
    return scores


class FlatSubstrateAdapter(ReferenceSubstrateAdapter):
    """Flat canonical-text Okapi BM25 baseline."""

    def _retrieval_text(self, artifact: CognitiveArtifact) -> str:
        return render_canonical_artifact(artifact)

    def _bounded_result(
        self,
        query: str,
        scored: list[RetrievedArtifact],
        budget: RetrievalBudget,
        logical_time: int,
    ) -> RetrievalResult:
        selected: list[RetrievedArtifact] = []
        used_chars = 0
        used_tokens = 0
        for item in scored:
            if len(selected) >= budget.max_items:
                break
            retrieval_text = self._retrieval_text(item.artifact)
            next_chars = used_chars + len(retrieval_text)
            next_tokens = used_tokens + len(_terms(retrieval_text))
            if budget.max_context_chars is not None and next_chars > budget.max_context_chars:
                continue
            if budget.max_context_tokens is not None and next_tokens > budget.max_context_tokens:
                continue
            selected.append(item)
            used_chars = next_chars
            used_tokens = next_tokens
        ids = tuple(item.artifact.artifact_id for item in selected)
        self._state.retrievals.append((logical_time, ids))
        self._state.reads += 1
        return RetrievalResult(
            query=query,
            logical_time=logical_time,
            items=tuple(selected),
            truncated=len(selected) < len(scored),
        )

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
        raw_scores = bm25_scores(query, [self._retrieval_text(row) for row in artifacts])
        ranked = sorted(
            (
                (score, artifact)
                for score, artifact in zip(raw_scores, artifacts)
                if score > 0
            ),
            key=lambda pair: (-pair[0], pair[1].artifact_id),
        )
        scored = [
            RetrievedArtifact(
                artifact,
                score,
                {"mode": "bm25", "rank": rank, "raw_score": score},
            )
            for rank, (score, artifact) in enumerate(ranked, start=1)
        ]
        return self._bounded_result(query, scored, budget, logical_time)

    def export_audit(self, decision_ref: str) -> AuditReceipt:
        raise UnsupportedCapabilityError(
            "flat canonical-text baseline does not export decision audit receipts"
        )

    def capability_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            adapter_name="flat-bm25",
            adapter_version="2.0.0",
            clock_mode=ClockMode.NATIVE,
            snapshot=True,
            branching=False,
            audit_export=False,
            agent_directed_capture=True,
            oracle_capture=True,
            usage_fidelity=UsageFidelity.COMPLETE,
            asynchronous_ingestion=False,
            notes=("relations are stored as evaluator-visible metadata sidecars",),
            evidence_mode=EvidenceMode.MAPPED,
            retrieval_representation=RetrievalRepresentation.CANONICAL,
        )
