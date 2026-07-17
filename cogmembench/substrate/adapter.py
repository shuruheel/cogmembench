from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from ..scenarios.schema import Event
from .schema import AuditReceipt, CognitiveArtifact, CognitiveRelation, RelationKind


class ClockMode(str, Enum):
    NATIVE = "native"
    MAPPED = "mapped"
    NONE = "none"


class UsageFidelity(str, Enum):
    COMPLETE = "complete"
    LOWER_BOUND = "lower_bound"
    UNAVAILABLE = "unavailable"


class EvidenceMode(str, Enum):
    """Where normalized benchmark evidence lives."""

    NATIVE = "native"
    MAPPED = "mapped"
    SIDECAR = "sidecar"


class RetrievalRepresentation(str, Enum):
    """Text exposed to the reasoning agent for a retrieved artifact."""

    CONTENT = "content"
    CANONICAL = "canonical"
    SUMMARY = "summary"


@dataclass(frozen=True)
class CapabilityManifest:
    adapter_name: str
    adapter_version: str
    clock_mode: ClockMode
    snapshot: bool
    branching: bool
    audit_export: bool
    agent_directed_capture: bool
    oracle_capture: bool
    usage_fidelity: UsageFidelity
    asynchronous_ingestion: bool = False
    max_context_items: int | None = None
    notes: tuple[str, ...] = ()
    evidence_mode: EvidenceMode = EvidenceMode.NATIVE
    automatic_capture: bool = True
    revision: bool = True
    relations: bool = True
    retrieval_representation: RetrievalRepresentation = RetrievalRepresentation.CONTENT

    def __post_init__(self) -> None:
        if not self.adapter_name or not self.adapter_version:
            raise ValueError("adapter_name and adapter_version are required")
        if self.max_context_items is not None and self.max_context_items <= 0:
            raise ValueError("max_context_items must be positive")
        if self.evidence_mode is EvidenceMode.SIDECAR and self.oracle_capture:
            raise ValueError("sidecar state cannot be declared as substrate oracle capture")


@dataclass(frozen=True)
class UsageReport:
    fidelity: UsageFidelity
    model_calls: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    embedding_calls: int | None = None
    read_operations: int | None = None
    write_operations: int | None = None
    storage_bytes: int | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        numeric = (
            self.model_calls,
            self.input_tokens,
            self.output_tokens,
            self.embedding_calls,
            self.read_operations,
            self.write_operations,
            self.storage_bytes,
        )
        if any(value is not None and value < 0 for value in numeric):
            raise ValueError("usage counters cannot be negative")
        if self.fidelity is UsageFidelity.UNAVAILABLE:
            if not self.reason:
                raise ValueError("unavailable usage reports require a reason")
            if any(value is not None for value in numeric):
                raise ValueError("unavailable usage counters must be None, never silent zeros")


@dataclass(frozen=True)
class RetrievalBudget:
    max_items: int
    max_context_tokens: int | None = None
    max_context_chars: int | None = None

    def __post_init__(self) -> None:
        if self.max_items <= 0:
            raise ValueError("max_items must be positive")
        for name, value in (
            ("max_context_tokens", self.max_context_tokens),
            ("max_context_chars", self.max_context_chars),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True)
class RetrievedArtifact:
    artifact: CognitiveArtifact
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    logical_time: int
    items: tuple[RetrievedArtifact, ...]
    truncated: bool = False


@dataclass(frozen=True)
class SnapshotResult:
    snapshot_id: str
    valid_at: int | None
    known_at: int | None
    artifacts: tuple[CognitiveArtifact, ...]
    relations: tuple[CognitiveRelation, ...]


class SubstrateError(RuntimeError):
    """Base class for representation-neutral adapter errors."""


class UnsupportedCapabilityError(SubstrateError):
    pass


class IsolationError(SubstrateError):
    pass


class ClockOrderError(SubstrateError):
    pass


@runtime_checkable
class SubstrateAdapter(Protocol):
    """Synchronous v2 adapter surface; ``quiesce`` is the ingestion barrier."""

    def reset(self, namespace: str) -> None: ...

    def quiesce(self) -> None: ...

    def close_session(self, session_id: str, logical_time: int) -> None: ...

    def observe(self, event: Event, logical_time: int) -> CognitiveArtifact: ...

    def commit(self, artifact: CognitiveArtifact, logical_time: int) -> CognitiveArtifact: ...

    def revise(
        self,
        artifact_id: str,
        revision: CognitiveArtifact,
        logical_time: int,
    ) -> CognitiveArtifact: ...

    def link(
        self,
        source_id: str,
        relation: RelationKind,
        target_id: str,
        logical_time: int,
        *,
        strength: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CognitiveRelation: ...

    def retrieve(
        self,
        query: str,
        budget: RetrievalBudget,
        logical_time: int,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> RetrievalResult: ...

    def snapshot(
        self,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> SnapshotResult: ...

    def export_audit(self, decision_ref: str) -> AuditReceipt: ...

    def usage_report(self) -> UsageReport: ...

    def capability_manifest(self) -> CapabilityManifest: ...
