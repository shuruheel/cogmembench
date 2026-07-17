from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class DerivationNodeKind(str, Enum):
    PREMISE = "premise"
    INTERMEDIATE = "intermediate"
    CONCLUSION = "conclusion"
    DECISION = "decision"


@dataclass(frozen=True)
class DerivationNode:
    artifact_id: str
    kind: DerivationNodeKind
    input_ids: tuple[str, ...]
    session_id: str
    token_count: int
    required_for_reuse: bool = False

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.session_id:
            raise ValueError("derivation nodes require artifact_id and session_id")
        if self.token_count <= 0:
            raise ValueError("derivation node token_count must be positive")
        if self.kind is DerivationNodeKind.PREMISE and self.input_ids:
            raise ValueError("premise nodes cannot have derivation inputs")
        if self.kind is not DerivationNodeKind.PREMISE and not self.input_ids:
            raise ValueError("derived nodes require at least one input")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DerivationNode:
        return cls(
            artifact_id=str(data["artifact_id"]),
            kind=DerivationNodeKind(data["kind"]),
            input_ids=tuple(data["input_ids"]),
            session_id=str(data["session_id"]),
            token_count=int(data["token_count"]),
            required_for_reuse=bool(data.get("required_for_reuse", False)),
        )


@dataclass(frozen=True)
class DerivationDAG:
    nodes: tuple[DerivationNode, ...]

    def __post_init__(self) -> None:
        by_id = {node.artifact_id: node for node in self.nodes}
        if len(by_id) != len(self.nodes):
            raise ValueError("derivation artifact IDs must be unique")
        for node in self.nodes:
            missing = set(node.input_ids) - set(by_id)
            if missing:
                raise ValueError(
                    f"derivation node {node.artifact_id} has missing inputs: {missing}"
                )
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(artifact_id: str) -> None:
            if artifact_id in visiting:
                raise ValueError("derivation graph must be acyclic")
            if artifact_id in visited:
                return
            visiting.add(artifact_id)
            for input_id in by_id[artifact_id].input_ids:
                visit(input_id)
            visiting.remove(artifact_id)
            visited.add(artifact_id)

        for artifact_id in by_id:
            visit(artifact_id)

    def depth(self, artifact_id: str) -> int:
        by_id = {node.artifact_id: node for node in self.nodes}
        if artifact_id not in by_id:
            raise KeyError(artifact_id)
        memo: dict[str, int] = {}

        def calculate(current: str) -> int:
            if current not in memo:
                inputs = by_id[current].input_ids
                memo[current] = 0 if not inputs else 1 + max(calculate(value) for value in inputs)
            return memo[current]

        return calculate(artifact_id)

    def breadth(self) -> int:
        return max((len(node.input_ids) for node in self.nodes), default=0)

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": [node.to_dict() for node in self.nodes]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DerivationDAG:
        return cls(tuple(DerivationNode.from_dict(row) for row in data["nodes"]))


@dataclass(frozen=True)
class ReDerivabilityControl:
    read_budget_tokens: int
    raw_premise_tokens: int
    derived_artifact_tokens: int
    premise_session_count: int
    minimum_budget_asymmetry: float = 2.0
    minimum_session_dispersion: int = 4

    def __post_init__(self) -> None:
        if (
            min(
                self.read_budget_tokens,
                self.raw_premise_tokens,
                self.derived_artifact_tokens,
                self.premise_session_count,
            )
            <= 0
        ):
            raise ValueError("re-derivability control values must be positive")
        if self.raw_premise_tokens / self.read_budget_tokens < self.minimum_budget_asymmetry:
            raise ValueError("raw premises do not meet the budget-asymmetry threshold")
        if self.derived_artifact_tokens > self.read_budget_tokens:
            raise ValueError("derived artifact must fit within the read budget")
        if self.premise_session_count < self.minimum_session_dispersion:
            raise ValueError("premises do not meet the session-dispersion threshold")

    @property
    def budget_asymmetry(self) -> float:
        return self.raw_premise_tokens / self.read_budget_tokens

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReDerivabilityControl:
        return cls(**data)
