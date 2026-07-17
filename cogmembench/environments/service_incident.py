from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from ..difficulty import DifficultyTier, difficulty_for_variant


class ActionKind(str, Enum):
    INSPECT = "inspect"
    PROBE_DEPENDENCY = "probe_dependency"
    REMEDIATE = "remediate"


@dataclass(frozen=True)
class IncidentAction:
    kind: ActionKind
    target: str
    detail: str = ""


@dataclass(frozen=True)
class EnvironmentObservation:
    step: int
    action: IncidentAction
    message: str
    signals: tuple[str, ...]
    cost: int
    total_cost: int
    resolved: bool


@dataclass(frozen=True)
class EnvironmentSnapshot:
    snapshot_id: str
    world_id: str
    step: int
    resolved: bool
    total_cost: int
    history: tuple[EnvironmentObservation, ...]


@dataclass(frozen=True)
class IncidentWorld:
    world_id: str
    services: tuple[str, ...]
    dependencies: tuple[tuple[str, str], ...]
    alert_service: str
    root_service: str
    root_cause: str
    root_signal: str
    correct_remediation: str
    distractor_remediations: tuple[str, ...]
    difficulty_tier: str = DifficultyTier.EASY.value
    realization_pattern: str = "direct-fanout"

    def __post_init__(self) -> None:
        service_set = set(self.services)
        if len(service_set) != len(self.services):
            raise ValueError("service IDs must be unique")
        if self.alert_service not in service_set or self.root_service not in service_set:
            raise ValueError("alert and root services must belong to the world")
        if any(
            left not in service_set or right not in service_set for left, right in self.dependencies
        ):
            raise ValueError("dependency endpoints must belong to the world")
        if self.correct_remediation in self.distractor_remediations:
            raise ValueError("correct remediation cannot also be a distractor")

    def public_brief(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "services": list(self.services),
            "dependencies": [list(edge) for edge in self.dependencies],
            "alert": f"elevated errors at {self.alert_service}",
            "available_remediations": sorted(
                (self.correct_remediation, *self.distractor_remediations)
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IncidentWorld:
        values = dict(data)
        values["services"] = tuple(values["services"])
        values["dependencies"] = tuple(tuple(edge) for edge in values["dependencies"])
        values["distractor_remediations"] = tuple(values["distractor_remediations"])
        return cls(**values)


INCIDENT_CASES = (
    "database",
    "cache",
    "gateway",
    "worker",
    "search",
)


def _incident_case(role: str, rng: random.Random) -> tuple[str, str, str]:
    """Instantiate a causal mechanism with seeded, outcome-relevant parameters."""
    if role == "database":
        pool_limit = 64 + 8 * rng.randrange(4, 25)
        return (
            f"database connection exhaustion at pool limit {pool_limit}",
            f"active connections pinned at pool limit {pool_limit}",
            f"increase database connection capacity above {pool_limit}",
        )
    if role == "cache":
        namespace = f"catalog-{rng.randrange(100, 1000)}"
        checksum = f"c{rng.randrange(1000, 10000)}"
        return (
            f"poisoned cache entries in namespace {namespace}",
            f"cache hits in {namespace} return invalid payload checksum {checksum}",
            f"flush poisoned cache namespace {namespace}",
        )
    if role == "gateway":
        certificate = f"edge-{rng.randrange(1000, 10000)}"
        return (
            f"expired upstream certificate {certificate}",
            f"TLS handshake reports certificate {certificate} expired",
            f"rotate gateway certificate {certificate}",
        )
    if role == "worker":
        consumer = f"consumer-{rng.randrange(10, 100)}"
        partition = rng.randrange(1, 33)
        return (
            f"queue consumer deadlock in {consumer}",
            f"partition {partition} depth rises while {consumer} throughput is zero",
            f"restart deadlocked queue consumer {consumer}",
        )
    shard = rng.randrange(1, 65)
    replica = rng.randrange(2, 8)
    return (
        f"search index shard {shard} unavailable",
        f"search shard {shard} is unavailable and replica {replica} is stale",
        f"promote healthy search replica for shard {shard}",
    )


def _service_graph(
    token: str, tier: DifficultyTier
) -> tuple[dict[str, str], tuple[tuple[str, str], ...], str]:
    backend_roles = ("gateway", "cache", "database", "worker", "search")
    roles = ["frontend", "api", *backend_roles]
    if tier is DifficultyTier.MEDIUM:
        roles.append("router")
    elif tier is DifficultyTier.HARD:
        roles.extend(("edge", "orchestrator"))
    services = {role: f"{role}-{token}" for role in roles}
    if tier is DifficultyTier.EASY:
        dependencies = (
            (services["frontend"], services["api"]),
            *((services["api"], services[role]) for role in backend_roles),
        )
        pattern = "direct-fanout"
    elif tier is DifficultyTier.MEDIUM:
        dependencies = (
            (services["frontend"], services["api"]),
            (services["api"], services["router"]),
            *((services["router"], services[role]) for role in backend_roles),
        )
        pattern = "routed-fanout"
    else:
        dependencies = (
            (services["frontend"], services["edge"]),
            (services["edge"], services["api"]),
            (services["api"], services["orchestrator"]),
            *((services["orchestrator"], services[role]) for role in backend_roles),
        )
        pattern = "layered-fanout"
    return services, tuple(dependencies), pattern


def generate_incident_world(seed: int, variant: int = 0) -> IncidentWorld:
    if variant < 0:
        raise ValueError("variant must be non-negative")
    rng = random.Random(seed * 1009 + variant)
    tier = difficulty_for_variant(variant)
    token = hashlib.sha256(f"incident:{seed}:{variant}".encode()).hexdigest()[:6]
    services_by_role, dependencies, pattern = _service_graph(token, tier)
    root_role = INCIDENT_CASES[(seed + variant) % len(INCIDENT_CASES)]
    root_cause, signal, remediation = _incident_case(root_role, rng)
    distractors = (
        f"restart {services_by_role['api']}",
        f"flush healthy cache on {services_by_role['cache']}",
        f"rotate unrelated certificate on {services_by_role['gateway']}",
        f"scale healthy worker {services_by_role['worker']}",
    )
    shuffled = list(distractors)
    rng.shuffle(shuffled)
    return IncidentWorld(
        world_id=f"incident-{seed}-{variant:02d}",
        services=tuple(services_by_role.values()),
        dependencies=dependencies,
        alert_service=services_by_role["frontend"],
        root_service=services_by_role[root_role],
        root_cause=root_cause,
        root_signal=signal,
        correct_remediation=remediation,
        distractor_remediations=tuple(shuffled),
        difficulty_tier=tier.value,
        realization_pattern=pattern,
    )


class ServiceIncidentEnvironment:
    """Deterministic incident simulator with replay and isolated snapshot branches."""

    ACTION_COSTS = {
        ActionKind.INSPECT: 1,
        ActionKind.PROBE_DEPENDENCY: 2,
        ActionKind.REMEDIATE: 5,
    }

    def __init__(self, world: IncidentWorld):
        self.world = world
        self._history: list[EnvironmentObservation] = []
        self._resolved = False
        self._total_cost = 0

    @property
    def resolved(self) -> bool:
        return self._resolved

    @property
    def total_cost(self) -> int:
        return self._total_cost

    @property
    def history(self) -> tuple[EnvironmentObservation, ...]:
        return tuple(self._history)

    def reset(self) -> None:
        self._history.clear()
        self._resolved = False
        self._total_cost = 0

    def _depends_on_root(self, service: str) -> bool:
        frontier = [service]
        visited = set()
        adjacency: dict[str, list[str]] = {}
        for source, target in self.world.dependencies:
            adjacency.setdefault(source, []).append(target)
        while frontier:
            current = frontier.pop()
            if current in visited:
                continue
            visited.add(current)
            if current == self.world.root_service:
                return True
            frontier.extend(adjacency.get(current, ()))
        return False

    def _inspect(self, target: str) -> tuple[str, tuple[str, ...]]:
        if self._resolved:
            return f"{target} metrics are healthy after remediation", ("healthy",)
        if target == self.world.root_service:
            return self.world.root_signal, ("root-signal", self.world.root_cause)
        if self._depends_on_root(target):
            return f"{target} shows downstream errors with upstream latency", (
                "downstream-symptom",
            )
        return f"{target} metrics are within normal bounds", ("healthy",)

    def _probe(self, source: str, target: str) -> tuple[str, tuple[str, ...]]:
        if (source, target) not in self.world.dependencies:
            raise ValueError(f"{source} does not directly depend on {target}")
        if not self._resolved and self._depends_on_root(target):
            return f"probe {source} -> {target} reproduces the failure", ("degraded-edge",)
        return f"probe {source} -> {target} succeeds", ("healthy-edge",)

    def _remediate(self, target: str, detail: str) -> tuple[str, tuple[str, ...]]:
        if self._resolved:
            return "incident is already resolved; remediation made no change", ("no-op",)
        if target == self.world.root_service and detail == self.world.correct_remediation:
            self._resolved = True
            return f"{detail} resolved the incident", ("resolved",)
        return f"{detail or 'remediation'} did not resolve the incident", (
            "unresolved",
            "wrong-remediation",
        )

    def step(self, action: IncidentAction) -> EnvironmentObservation:
        if action.target not in self.world.services:
            raise ValueError(f"unknown service: {action.target}")
        cost = self.ACTION_COSTS[action.kind]
        if action.kind is ActionKind.INSPECT:
            message, signals = self._inspect(action.target)
        elif action.kind is ActionKind.PROBE_DEPENDENCY:
            if not action.detail:
                raise ValueError("dependency probes require the target dependency in detail")
            message, signals = self._probe(action.target, action.detail)
        elif action.kind is ActionKind.REMEDIATE:
            if not action.detail:
                raise ValueError("remediation actions require a remediation detail")
            message, signals = self._remediate(action.target, action.detail)
        else:
            raise ValueError(f"unsupported action kind: {action.kind}")
        self._total_cost += cost
        observation = EnvironmentObservation(
            step=len(self._history),
            action=action,
            message=message,
            signals=signals,
            cost=cost,
            total_cost=self._total_cost,
            resolved=self._resolved,
        )
        self._history.append(observation)
        return observation

    def snapshot(self) -> EnvironmentSnapshot:
        payload = {
            "world_id": self.world.world_id,
            "resolved": self._resolved,
            "total_cost": self._total_cost,
            "history": [asdict(item) for item in self._history],
        }
        raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return EnvironmentSnapshot(
            snapshot_id=f"incident-snapshot:{hashlib.sha256(raw.encode()).hexdigest()[:16]}",
            world_id=self.world.world_id,
            step=len(self._history),
            resolved=self._resolved,
            total_cost=self._total_cost,
            history=tuple(self._history),
        )

    def branch(self, snapshot: EnvironmentSnapshot) -> ServiceIncidentEnvironment:
        if snapshot.world_id != self.world.world_id:
            raise ValueError("snapshot belongs to a different incident world")
        branch = ServiceIncidentEnvironment(self.world)
        branch._history = list(snapshot.history)
        branch._resolved = snapshot.resolved
        branch._total_cost = snapshot.total_cost
        return branch

    def replay(self, actions: list[IncidentAction]) -> tuple[EnvironmentObservation, ...]:
        self.reset()
        for action in actions:
            self.step(action)
        return self.history


def execution_score(environment: ServiceIncidentEnvironment) -> dict[str, float]:
    correct_actions = [
        observation
        for observation in environment.history
        if observation.action.kind is ActionKind.REMEDIATE
        and observation.action.target == environment.world.root_service
        and observation.action.detail == environment.world.correct_remediation
    ]
    minimum_cost = ServiceIncidentEnvironment.ACTION_COSTS[ActionKind.REMEDIATE]
    efficiency = minimum_cost / environment.total_cost if environment.total_cost else 0.0
    return {
        "execution_success": float(environment.resolved),
        "true_world_correctness": float(bool(correct_actions)),
        "cost_efficiency": min(1.0, efficiency),
        "total_action_cost": float(environment.total_cost),
    }
