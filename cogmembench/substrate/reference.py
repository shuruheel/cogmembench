from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from ..scenarios.schema import Event
from .adapter import (
    CapabilityManifest,
    ClockMode,
    ClockOrderError,
    IsolationError,
    RetrievalBudget,
    RetrievalResult,
    RetrievedArtifact,
    SnapshotResult,
    UsageFidelity,
    UsageReport,
)
from .schema import (
    ArtifactKind,
    AuditReceipt,
    CognitiveArtifact,
    CognitiveRelation,
    EpistemicStatus,
    RelationKind,
    TimeInterval,
    Visibility,
)

WORD = re.compile(r"[a-z0-9]+")


@dataclass
class _NamespaceState:
    artifacts: dict[str, CognitiveArtifact] = field(default_factory=dict)
    relations: dict[str, CognitiveRelation] = field(default_factory=dict)
    retrievals: list[tuple[int, tuple[str, ...]]] = field(default_factory=list)
    closed_sessions: dict[str, int] = field(default_factory=dict)
    last_logical_time: int = 0
    reads: int = 0
    writes: int = 0


class ReferenceSubstrateAdapter:
    """Deterministic, ledger-conformant adapter for contract tests and CI."""

    def __init__(self) -> None:
        self._namespaces: dict[str, _NamespaceState] = {}
        self._namespace: str | None = None

    @property
    def _state(self) -> _NamespaceState:
        if self._namespace is None:
            raise IsolationError("reset(namespace) must be called before using the adapter")
        return self._namespaces[self._namespace]

    def reset(self, namespace: str) -> None:
        if not namespace.strip():
            raise IsolationError("namespace must be non-empty")
        self._namespaces[namespace] = _NamespaceState()
        self._namespace = namespace

    def _advance(self, logical_time: int) -> None:
        if isinstance(logical_time, bool) or not isinstance(logical_time, int) or logical_time < 0:
            raise ClockOrderError("logical_time must be a non-negative integer")
        if logical_time < self._state.last_logical_time:
            raise ClockOrderError(
                f"logical time moved backward: {logical_time} < {self._state.last_logical_time}"
            )
        self._state.last_logical_time = logical_time

    def quiesce(self) -> None:
        return None

    def close_session(self, session_id: str, logical_time: int) -> None:
        self._advance(logical_time)
        existing = self._state.closed_sessions.get(session_id)
        if existing is not None and existing != logical_time:
            raise ValueError(f"session {session_id!r} is already closed at {existing}")
        self._state.closed_sessions[session_id] = logical_time

    def observe(self, event: Event, logical_time: int) -> CognitiveArtifact:
        if event.report_time is not None and event.report_time != logical_time:
            raise ClockOrderError("event.report_time must match the observe logical_time")
        event_id = event.event_id or f"event:{event.session_id}:{event.turn_id}"
        valid_start = event.event_time if event.event_time is not None else logical_time
        artifact = CognitiveArtifact(
            artifact_id=event_id,
            kind=ArtifactKind.OBSERVATION,
            content=event.content,
            scenario_id=self._namespace or "",
            valid_time=TimeInterval(valid_start),
            epistemic_status=EpistemicStatus.ACCEPTED,
            actor_id=event.role,
            session_id=event.session_id,
            turn_id=event.turn_id,
            provenance_event_ids=(event_id,),
            visibility=Visibility.PUBLIC,
        )
        return self.commit(artifact, logical_time)

    def commit(self, artifact: CognitiveArtifact, logical_time: int) -> CognitiveArtifact:
        self._advance(logical_time)
        if artifact.scenario_id != self._namespace:
            raise IsolationError(
                f"artifact scenario {artifact.scenario_id!r} does not match namespace "
                f"{self._namespace!r}"
            )
        transaction_time = artifact.transaction_time or TimeInterval(logical_time)
        if transaction_time.start != logical_time:
            raise ClockOrderError("transaction_time.start must match the commit logical_time")
        stored = replace(artifact, transaction_time=transaction_time)
        existing = self._state.artifacts.get(stored.artifact_id)
        if existing is not None:
            if existing == stored:
                return existing
            raise ValueError(f"artifact ID conflict: {stored.artifact_id}")
        self._state.artifacts[stored.artifact_id] = stored
        self._state.writes += 1
        return stored

    def revise(
        self,
        artifact_id: str,
        revision: CognitiveArtifact,
        logical_time: int,
    ) -> CognitiveArtifact:
        self._advance(logical_time)
        previous = self._state.artifacts.get(artifact_id)
        if previous is None:
            raise KeyError(artifact_id)
        if previous.transaction_time is None:
            raise ValueError("stored artifact has no transaction time")
        if previous.transaction_time.end is not None:
            existing = self._state.artifacts.get(revision.artifact_id)
            expected = replace(
                revision,
                revision_of=artifact_id,
                transaction_time=revision.transaction_time or TimeInterval(logical_time),
            )
            if existing is not None and existing == expected:
                return existing
            raise ValueError(f"artifact {artifact_id!r} has already been revised")
        if revision.revision_of not in {None, artifact_id}:
            raise ValueError("revision_of must identify the revised artifact")
        self._state.artifacts[artifact_id] = replace(
            previous,
            transaction_time=previous.transaction_time.close(logical_time),
        )
        stored = self.commit(
            replace(revision, revision_of=artifact_id),
            logical_time,
        )
        self.link(
            stored.artifact_id,
            RelationKind.SUPERSEDES,
            artifact_id,
            logical_time,
        )
        return stored

    def link(
        self,
        source_id: str,
        relation: RelationKind,
        target_id: str,
        logical_time: int,
        *,
        strength: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CognitiveRelation:
        self._advance(logical_time)
        for artifact_id in (source_id, target_id):
            if artifact_id not in self._state.artifacts:
                raise KeyError(artifact_id)
        digest = hashlib.sha256(
            f"{source_id}\0{relation.value}\0{target_id}\0{logical_time}".encode()
        ).hexdigest()[:16]
        row = CognitiveRelation(
            relation_id=f"relation:{digest}",
            source_id=source_id,
            kind=relation,
            target_id=target_id,
            created_at=logical_time,
            strength=strength,
            source="reference-adapter",
            metadata=metadata or {},
        )
        existing = self._state.relations.get(row.relation_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError(f"relation ID conflict: {row.relation_id}")
        self._state.relations[row.relation_id] = row
        self._state.writes += 1
        return row

    def _visible_artifacts(
        self,
        valid_at: int | None,
        known_at: int | None,
    ) -> list[CognitiveArtifact]:
        knowledge_time = self._state.last_logical_time if known_at is None else known_at
        return [
            artifact
            for artifact in self._state.artifacts.values()
            if artifact.transaction_time is not None
            and artifact.transaction_time.contains(knowledge_time)
            and (valid_at is None or artifact.valid_time.contains(valid_at))
        ]

    def _retrieval_text(self, artifact: CognitiveArtifact) -> str:
        return artifact.content

    def retrieve(
        self,
        query: str,
        budget: RetrievalBudget,
        logical_time: int,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> RetrievalResult:
        self._advance(logical_time)
        query_terms = set(WORD.findall(query.lower()))
        scored: list[RetrievedArtifact] = []
        for artifact in self._visible_artifacts(valid_at, known_at):
            retrieval_text = self._retrieval_text(artifact)
            terms = set(WORD.findall(retrieval_text.lower()))
            overlap = len(query_terms & terms)
            if overlap:
                scored.append(RetrievedArtifact(artifact, overlap / len(query_terms or {""})))
        scored.sort(key=lambda item: (-item.score, item.artifact.artifact_id))
        candidates = scored
        selected: list[RetrievedArtifact] = []
        used_chars = 0
        used_tokens = 0
        for item in candidates:
            if len(selected) >= budget.max_items:
                break
            retrieval_text = self._retrieval_text(item.artifact)
            next_chars = used_chars + len(retrieval_text)
            next_tokens = used_tokens + len(WORD.findall(retrieval_text.lower()))
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
            truncated=len(selected) < len(candidates),
        )

    def snapshot(
        self,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> SnapshotResult:
        knowledge_time = self._state.last_logical_time if known_at is None else known_at
        artifacts = tuple(
            sorted(
                self._visible_artifacts(valid_at, knowledge_time),
                key=lambda artifact: artifact.artifact_id,
            )
        )
        relations = tuple(
            sorted(
                (
                    relation
                    for relation in self._state.relations.values()
                    if relation.created_at <= knowledge_time
                    and (
                        valid_at is None
                        or relation.valid_time is None
                        or relation.valid_time.contains(valid_at)
                    )
                ),
                key=lambda relation: relation.relation_id,
            )
        )
        raw = json.dumps(
            {
                "namespace": self._namespace,
                "valid_at": valid_at,
                "known_at": knowledge_time,
                "artifact_ids": [artifact.artifact_id for artifact in artifacts],
                "relation_ids": [relation.relation_id for relation in relations],
            },
            sort_keys=True,
        )
        snapshot_id = f"snapshot:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
        self._state.reads += 1
        return SnapshotResult(snapshot_id, valid_at, knowledge_time, artifacts, relations)

    def export_audit(self, decision_ref: str) -> AuditReceipt:
        decision = self._state.artifacts.get(decision_ref)
        if decision is None:
            raise KeyError(decision_ref)
        if decision.kind is not ArtifactKind.DECISION:
            raise ValueError(f"artifact {decision_ref!r} is not a decision")
        if decision.transaction_time is None:
            raise ValueError("decision has no transaction time")
        related = [
            relation
            for relation in self._state.relations.values()
            if relation.target_id == decision_ref
            and relation.created_at <= decision.transaction_time.start
        ]
        evidence = tuple(
            sorted(
                relation.source_id for relation in related if relation.kind is RelationKind.SUPPORTS
            )
        )
        intermediate = tuple(
            sorted(
                relation.source_id
                for relation in related
                if relation.kind in {RelationKind.DERIVED_FROM, RelationKind.DEPENDS_ON}
            )
        )
        claimed_retrievals = tuple(
            str(value) for value in decision.structured_content.get("retrieved_artifact_ids", ())
        )
        observed_before_decision = {
            artifact_id
            for time, ids in self._state.retrievals
            if time <= decision.transaction_time.start
            for artifact_id in ids
        }
        explicit_retrievals = tuple(
            artifact_id
            for artifact_id in claimed_retrievals
            if artifact_id in observed_before_decision
        )
        retrieval_times = tuple(
            time
            for time, ids in self._state.retrievals
            if time <= decision.transaction_time.start and set(ids) & set(explicit_retrievals)
        )
        later_revisions = tuple(
            sorted(
                artifact.artifact_id
                for artifact in self._state.artifacts.values()
                if artifact.revision_of == decision_ref
            )
        )
        self._state.reads += 1
        return AuditReceipt(
            decision_ref=decision_ref,
            decision_time=decision.transaction_time.start,
            evidence_ids=evidence,
            intermediate_artifact_ids=intermediate,
            source_event_ids=decision.provenance_event_ids,
            retrieved_artifact_ids=explicit_retrievals,
            retrieval_times=retrieval_times,
            assumptions=tuple(decision.structured_content.get("assumptions", ())),
            alternatives=tuple(decision.structured_content.get("alternatives", ())),
            later_revision_ids=later_revisions,
        )

    def usage_report(self) -> UsageReport:
        payload = {
            "artifacts": [asdict(row) for row in self._state.artifacts.values()],
            "relations": [asdict(row) for row in self._state.relations.values()],
        }
        return UsageReport(
            fidelity=UsageFidelity.COMPLETE,
            model_calls=0,
            input_tokens=0,
            output_tokens=0,
            embedding_calls=0,
            read_operations=self._state.reads,
            write_operations=self._state.writes,
            storage_bytes=len(json.dumps(payload, sort_keys=True, default=str).encode()),
        )

    def capability_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            adapter_name="reference",
            adapter_version="2.0.0",
            clock_mode=ClockMode.NATIVE,
            snapshot=True,
            branching=False,
            audit_export=True,
            agent_directed_capture=True,
            oracle_capture=True,
            usage_fidelity=UsageFidelity.COMPLETE,
            asynchronous_ingestion=False,
        )
