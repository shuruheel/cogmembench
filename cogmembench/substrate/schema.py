from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


def _validate_logical_time(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


class ArtifactKind(str, Enum):
    SOURCE = "source"
    OBSERVATION = "observation"
    EVENT = "event"
    EVIDENCE = "evidence"
    CLAIM = "claim"
    HYPOTHESIS = "hypothesis"
    CONCLUSION = "conclusion"
    ASSUMPTION = "assumption"
    OPEN_QUESTION = "open_question"
    GOAL = "goal"
    CONSTRAINT = "constraint"
    OPTION = "option"
    DECISION = "decision"
    PLAN = "plan"
    DEFERRED_INTENTION = "deferred_intention"
    ACTION = "action"
    EXECUTION = "execution"
    OUTCOME = "outcome"
    FAILURE = "failure"
    LESSON = "lesson"
    RULE = "rule"
    POLICY = "policy"


class EpistemicStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    UNCERTAIN = "uncertain"
    REJECTED = "rejected"
    STALE = "stale"
    SUPERSEDED = "superseded"


class RelationKind(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    DEPENDS_ON = "depends_on"
    SUPERSEDES = "supersedes"
    MOTIVATES = "motivates"
    IMPLEMENTS = "implements"
    PRODUCES = "produces"
    LEARNED_FROM = "learned_from"
    APPLIES_TO = "applies_to"
    INVALIDATES = "invalidates"


class Visibility(str, Enum):
    PUBLIC = "public"
    AGENT = "agent"
    EVALUATOR_ONLY = "evaluator_only"


@dataclass(frozen=True)
class TimeInterval:
    """Half-open logical-time interval ``[start, end)``; ``None`` means unbounded."""

    start: int
    end: int | None = None

    def __post_init__(self) -> None:
        _validate_logical_time("start", self.start)
        if self.end is not None:
            _validate_logical_time("end", self.end)
            if self.end <= self.start:
                raise ValueError("end must be greater than start")

    def contains(self, logical_time: int) -> bool:
        _validate_logical_time("logical_time", logical_time)
        return self.start <= logical_time and (self.end is None or logical_time < self.end)

    def close(self, logical_time: int) -> TimeInterval:
        _validate_logical_time("logical_time", logical_time)
        if self.end is not None:
            if self.end == logical_time:
                return self
            raise ValueError("interval is already closed")
        return TimeInterval(self.start, logical_time)


@dataclass(frozen=True)
class CognitiveArtifact:
    artifact_id: str
    kind: ArtifactKind
    content: str
    scenario_id: str
    valid_time: TimeInterval
    transaction_time: TimeInterval | None = None
    structured_content: dict[str, Any] = field(default_factory=dict)
    entity_scope: tuple[str, ...] = ()
    epistemic_status: EpistemicStatus = EpistemicStatus.PROPOSED
    confidence: float | None = None
    actor_id: str = ""
    session_id: str = ""
    turn_id: int | None = None
    provenance_event_ids: tuple[str, ...] = ()
    revision_of: str | None = None
    visibility: Visibility = Visibility.AGENT

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("artifact_id is required")
        if not self.scenario_id:
            raise ValueError("scenario_id is required")
        if not self.content:
            raise ValueError("content is required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.turn_id is not None and (isinstance(self.turn_id, bool) or self.turn_id < 0):
            raise ValueError("turn_id must be a non-negative integer or None")


@dataclass(frozen=True)
class CognitiveRelation:
    relation_id: str
    source_id: str
    kind: RelationKind
    target_id: str
    created_at: int
    valid_time: TimeInterval | None = None
    strength: float | None = None
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.relation_id or not self.source_id or not self.target_id:
            raise ValueError("relation_id, source_id, and target_id are required")
        _validate_logical_time("created_at", self.created_at)
        if self.strength is not None and not 0.0 <= self.strength <= 1.0:
            raise ValueError("strength must be between 0 and 1")


@dataclass(frozen=True)
class AuditReceipt:
    decision_ref: str
    decision_time: int
    evidence_ids: tuple[str, ...] = ()
    intermediate_artifact_ids: tuple[str, ...] = ()
    source_event_ids: tuple[str, ...] = ()
    retrieved_artifact_ids: tuple[str, ...] = ()
    retrieval_times: tuple[int, ...] = ()
    assumptions: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    later_revision_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.decision_ref:
            raise ValueError("decision_ref is required")
        _validate_logical_time("decision_time", self.decision_time)
        for value in self.retrieval_times:
            _validate_logical_time("retrieval_time", value)
