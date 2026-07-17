from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any

WORD = re.compile(r"[a-z0-9]+")


@dataclass
class FlatRecord:
    memory_id: str
    text: str
    session_id: str
    metadata: dict[str, Any]


class FlatMemoryStore:
    """Small auditable Okapi BM25 baseline; no cognitive types or relations."""

    backend_label = "flat-bm25"

    def __init__(self):
        self.records: list[FlatRecord] = []

    def reset(self) -> None:
        self.records.clear()

    def add(self, text: str, session_id: str, metadata: dict[str, Any] | None = None) -> FlatRecord:
        record = FlatRecord(f"flat-{len(self.records):06d}", text, session_id, metadata or {})
        self.records.append(record)
        return record

    @staticmethod
    def _terms(text: str) -> list[str]:
        return WORD.findall(text.lower())

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        if not self.records:
            return []
        docs = [self._terms(record.text) for record in self.records]
        qterms = set(self._terms(query))
        avgdl = sum(map(len, docs)) / len(docs) or 1
        scores: list[tuple[float, int]] = []
        for i, terms in enumerate(docs):
            score = 0.0
            for term in qterms:
                tf = terms.count(term)
                if not tf:
                    continue
                df = sum(term in doc for doc in docs)
                idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
                score += idf * tf * 2.5 / (tf + 1.5 * (1 - 0.75 + 0.75 * len(terms) / avgdl))
            if score:
                scores.append((score, i))
        scores.sort(key=lambda item: (-item[0], self.records[item[1]].memory_id))
        return [{**asdict(self.records[i]), "score": score} for score, i in scores[:k]]

    def snapshot(self) -> dict[str, Any]:
        return {"backend": self.backend_label, "records": [asdict(record) for record in self.records], "node_count": len(self.records), "edge_count": 0}


class FlatHybridMemoryStore(FlatMemoryStore):
    """Flat textual memory with BM25/vector reciprocal-rank fusion."""

    backend_label = "flat-hybrid"

    def __init__(self, embedding_provider: Any):
        super().__init__()
        self.embedding_provider = embedding_provider
        self.vectors: list[list[float]] = []

    def reset(self) -> None:
        super().reset()
        self.vectors.clear()

    def add_many(self, texts: list[str], session_id: str) -> list[FlatRecord]:
        vectors = self.embedding_provider.embed(texts)
        added = [super(FlatHybridMemoryStore, self).add(text, session_id) for text in texts]
        self.vectors.extend(vectors)
        return added

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        if not self.records:
            return []
        query_vector = self.embedding_provider.embed([query])[0]
        bm25 = super().search(query, len(self.records))
        bm25_rank = {row["memory_id"]: rank for rank, row in enumerate(bm25, start=1)}
        semantic = sorted(
            (
                (self._cosine(query_vector, vector), index)
                for index, vector in enumerate(self.vectors)
            ),
            key=lambda pair: (-pair[0], self.records[pair[1]].memory_id),
        )
        semantic_rank = {
            self.records[index].memory_id: rank
            for rank, (_, index) in enumerate(semantic, start=1)
        }
        fused: list[tuple[float, int, list[dict[str, Any]]]] = []
        for index, record in enumerate(self.records):
            legs = []
            score = 0.0
            if record.memory_id in bm25_rank:
                rank = bm25_rank[record.memory_id]
                score += 1 / (60 + rank)
                legs.append({"mode": "text", "rank": rank})
            if record.memory_id in semantic_rank:
                rank = semantic_rank[record.memory_id]
                score += 1 / (60 + rank)
                legs.append(
                    {
                        "mode": "semantic",
                        "rank": rank,
                        "score": self._cosine(query_vector, self.vectors[index]),
                    }
                )
            fused.append((score, index, legs))
        fused.sort(key=lambda item: (-item[0], self.records[item[1]].memory_id))
        return [
            {**asdict(self.records[index]), "score": score, "legs": legs}
            for score, index, legs in fused[:k]
        ]

    def telemetry(self) -> dict[str, Any]:
        return self.embedding_provider.telemetry()
