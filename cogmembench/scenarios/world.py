from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from ..substrate.schema import (
    ArtifactKind,
    CognitiveArtifact,
    EpistemicStatus,
    RelationKind,
    TimeInterval,
    Visibility,
)


class ScenarioPhase(str, Enum):
    ACCUMULATE = "accumulate"
    DERIVE = "derive"
    DECIDE = "decide"
    EXPERIENCE = "experience"
    CONSOLIDATE = "consolidate"
    REUSE = "reuse"
    PERTURB = "perturb"
    REPAIR = "repair"
    AUDIT = "audit"
    TIME_TRAVEL = "time_travel"


class LedgerOperation(str, Enum):
    COMMIT = "commit"
    REVISE = "revise"
    LINK = "link"


def artifact_to_dict(artifact: CognitiveArtifact) -> dict[str, Any]:
    data = asdict(artifact)
    data["kind"] = artifact.kind.value
    data["epistemic_status"] = artifact.epistemic_status.value
    data["visibility"] = artifact.visibility.value
    return data


def artifact_from_dict(data: dict[str, Any]) -> CognitiveArtifact:
    values = dict(data)
    values["kind"] = ArtifactKind(values["kind"])
    values["epistemic_status"] = EpistemicStatus(values["epistemic_status"])
    values["visibility"] = Visibility(values["visibility"])
    values["valid_time"] = TimeInterval(**values["valid_time"])
    if values.get("transaction_time") is not None:
        values["transaction_time"] = TimeInterval(**values["transaction_time"])
    for name in ("entity_scope", "provenance_event_ids"):
        values[name] = tuple(values.get(name, ()))
    return CognitiveArtifact(**values)


@dataclass(frozen=True)
class LedgerEntry:
    sequence: int
    logical_time: int
    phase: ScenarioPhase
    operation: LedgerOperation
    artifact: CognitiveArtifact | None = None
    target_id: str | None = None
    source_id: str | None = None
    relation: RelationKind | None = None
    strength: float | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0 or self.logical_time < 0:
            raise ValueError("ledger sequence and logical_time must be non-negative")
        if self.operation is LedgerOperation.COMMIT and self.artifact is None:
            raise ValueError("commit entries require an artifact")
        if self.operation is LedgerOperation.REVISE and (
            self.artifact is None or not self.target_id
        ):
            raise ValueError("revise entries require target_id and artifact")
        if self.operation is LedgerOperation.LINK and (
            not self.source_id or not self.target_id or self.relation is None
        ):
            raise ValueError("link entries require source_id, relation, and target_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "logical_time": self.logical_time,
            "phase": self.phase.value,
            "operation": self.operation.value,
            "artifact": artifact_to_dict(self.artifact) if self.artifact else None,
            "target_id": self.target_id,
            "source_id": self.source_id,
            "relation": self.relation.value if self.relation else None,
            "strength": self.strength,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LedgerEntry:
        return cls(
            sequence=int(data["sequence"]),
            logical_time=int(data["logical_time"]),
            phase=ScenarioPhase(data["phase"]),
            operation=LedgerOperation(data["operation"]),
            artifact=(artifact_from_dict(data["artifact"]) if data.get("artifact") else None),
            target_id=data.get("target_id"),
            source_id=data.get("source_id"),
            relation=RelationKind(data["relation"]) if data.get("relation") else None,
            strength=data.get("strength"),
            metadata=data.get("metadata"),
        )


@dataclass(frozen=True)
class WorldLedger:
    scenario_id: str
    entries: tuple[LedgerEntry, ...]
    schema_version: int = 2

    def __post_init__(self) -> None:
        if self.schema_version != 2:
            raise ValueError("only world-ledger schema version 2 is supported")
        if not self.scenario_id:
            raise ValueError("scenario_id is required")
        sequences = [entry.sequence for entry in self.entries]
        if sequences != list(range(len(self.entries))):
            raise ValueError("ledger sequences must be contiguous and start at zero")
        times = [entry.logical_time for entry in self.entries]
        if times != sorted(times):
            raise ValueError("ledger logical_time values must be monotonic")
        for entry in self.entries:
            if entry.artifact and entry.artifact.scenario_id != self.scenario_id:
                raise ValueError("ledger artifacts must match the ledger scenario_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldLedger:
        return cls(
            scenario_id=str(data["scenario_id"]),
            entries=tuple(LedgerEntry.from_dict(row) for row in data["entries"]),
            schema_version=int(data.get("schema_version", 2)),
        )


@dataclass(frozen=True)
class TemporalProbe:
    probe_id: str
    checkpoint_id: str
    valid_at: int
    known_at: int
    subject_key: str
    expected_artifact_id: str
    expected_value: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalProbe:
        return cls(**data)


@dataclass(frozen=True)
class RepairProbe:
    probe_id: str
    checkpoint_id: str
    known_at: int
    invalidated_artifact_ids: tuple[str, ...]
    preserved_artifact_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepairProbe:
        return cls(
            probe_id=str(data["probe_id"]),
            checkpoint_id=str(data["checkpoint_id"]),
            known_at=int(data["known_at"]),
            invalidated_artifact_ids=tuple(data["invalidated_artifact_ids"]),
            preserved_artifact_ids=tuple(data["preserved_artifact_ids"]),
        )


@dataclass(frozen=True)
class CognitiveWorld:
    ledger: WorldLedger
    temporal_probes: tuple[TemporalProbe, ...]
    repair_probe: RepairProbe

    def to_hidden_world(self) -> dict[str, Any]:
        return {
            "cognitive_world_schema": 2,
            "world_ledger": self.ledger.to_dict(),
            "temporal_probes": [probe.to_dict() for probe in self.temporal_probes],
            "repair_probe": self.repair_probe.to_dict(),
        }

    @classmethod
    def from_hidden_world(cls, data: dict[str, Any]) -> CognitiveWorld:
        if data.get("cognitive_world_schema") != 2:
            raise ValueError("scenario does not contain a cognitive-world schema v2 ledger")
        return cls(
            ledger=WorldLedger.from_dict(data["world_ledger"]),
            temporal_probes=tuple(TemporalProbe.from_dict(row) for row in data["temporal_probes"]),
            repair_probe=RepairProbe.from_dict(data["repair_probe"]),
        )
