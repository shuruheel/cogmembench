from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCENARIO_PHASES = {
    "accumulate",
    "derive",
    "decide",
    "experience",
    "consolidate",
    "reuse",
    "perturb",
    "repair",
    "audit",
    "time_travel",
}


@dataclass(frozen=True)
class Event:
    session_id: str
    turn_id: int
    role: str
    content: str
    evaluate: bool = False
    checkpoint_id: str | None = None
    event_time: int | None = None
    report_time: int | None = None
    event_id: str | None = None
    phase: str | None = None

    def __post_init__(self) -> None:
        for name, value in (("event_time", self.event_time), ("report_time", self.report_time)):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if self.phase is not None and self.phase not in SCENARIO_PHASES:
            raise ValueError(f"unknown scenario phase: {self.phase}")

    def to_dict(self, schema_version: int = 1) -> dict[str, Any]:
        data = asdict(self)
        if schema_version == 1:
            data.pop("event_time")
            data.pop("report_time")
            data.pop("event_id")
            data.pop("phase")
        return data


@dataclass(frozen=True)
class PublicScenario:
    scenario_id: str
    family: str
    seed: int
    variant: int
    events: tuple[Event, ...]
    max_agent_steps: int = 8
    schema_version: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.schema_version, bool) or self.schema_version not in {1, 2}:
            raise ValueError(f"unsupported scenario schema version: {self.schema_version}")
        if self.schema_version == 1:
            return
        report_times = [event.report_time for event in self.events]
        if any(event.event_time is None for event in self.events):
            raise ValueError("schema-v2 events require event_time")
        if any(value is None for value in report_times):
            raise ValueError("schema-v2 events require report_time")
        if any(not event.event_id for event in self.events):
            raise ValueError("schema-v2 events require event_id")
        if len({event.event_id for event in self.events}) != len(self.events):
            raise ValueError("schema-v2 event_id values must be unique")
        if any(event.phase is None for event in self.events):
            raise ValueError("schema-v2 events require phase")
        concrete_times = [value for value in report_times if value is not None]
        if concrete_times != sorted(concrete_times) or len(concrete_times) != len(
            set(concrete_times)
        ):
            raise ValueError("schema-v2 report_time values must be strictly increasing")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["events"] = [event.to_dict(self.schema_version) for event in self.events]
        if self.schema_version == 1:
            data.pop("schema_version")
        return data


@dataclass(frozen=True)
class ExpectedMemory:
    memory_id: str
    primitive: str
    text: str
    key: str = ""
    value: str = ""
    source_session: str = ""
    supersedes: str | None = None
    provenance: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpectedAction:
    session_id: str
    turn_id: int
    operation: str
    primitive: str = ""
    memory_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluatorSpec:
    expected_answer: dict[str, str]
    durable: tuple[ExpectedMemory, ...]
    expected_answers: dict[str, dict[str, str]] = field(default_factory=dict)
    expected_actions: tuple[ExpectedAction, ...] = ()
    obsolete_values: tuple[str, ...] = ()
    non_durable_terms: tuple[str, ...] = ()
    expected_retrieval_ids: tuple[str, ...] = ()
    expected_tool_ops: tuple[str, ...] = ()
    category: str = "continuity"


@dataclass(frozen=True)
class Scenario:
    public: PublicScenario
    evaluator: EvaluatorSpec
    hidden_world: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["public"] = self.public.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        public = data["public"]
        evaluator = data["evaluator"]
        return cls(
            public=PublicScenario(
                **{k: v for k, v in public.items() if k != "events"},
                events=tuple(Event(**e) for e in public["events"]),
            ),
            evaluator=EvaluatorSpec(
                **{k: v for k, v in evaluator.items() if k not in {"durable", "expected_actions"}},
                durable=tuple(ExpectedMemory(**m) for m in evaluator["durable"]),
                expected_actions=tuple(
                    ExpectedAction(**action) for action in evaluator.get("expected_actions", [])
                ),
            ),
            hidden_world=data.get("hidden_world", {}),
        )

    def public_hash(self) -> str:
        raw = json.dumps(self.public.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


def save_jsonl(path: Path, scenarios: list[Scenario]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for scenario in scenarios:
            fh.write(json.dumps(scenario.to_dict(), sort_keys=True))
            fh.write("\n")


def load_jsonl(path: Path) -> list[Scenario]:
    with path.open(encoding="utf-8") as fh:
        return [Scenario.from_dict(json.loads(line)) for line in fh if line.strip()]


def model_view(public: PublicScenario) -> dict[str, Any]:
    """The only scenario representation runner/provider code may receive."""
    return public.to_dict()
