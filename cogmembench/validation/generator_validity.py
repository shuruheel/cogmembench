from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from typing import Any, Iterable

from ..scenarios.schema import Scenario

CORE_FAMILIES = {
    "bitemporal_belief_revision",
    "recursive_investigation",
    "decision_lineage",
}


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _event_shape(scenario: Scenario) -> list[dict[str, Any]]:
    previous_time = 0
    rows = []
    for event in scenario.public.events:
        report_time = event.report_time or 0
        rows.append(
            {
                "phase": event.phase,
                "role": event.role,
                "evaluate": event.evaluate,
                "checkpoint": event.checkpoint_id,
                "report_delta": report_time - previous_time,
                "late_arrival": bool(
                    event.event_time is not None and event.event_time < report_time
                ),
            }
        )
        previous_time = report_time
    return rows


def _ledger_shape(hidden: dict[str, Any]) -> list[dict[str, Any]]:
    ledger = hidden.get("world_ledger", {})
    return [
        {
            "phase": row.get("phase"),
            "operation": row.get("operation"),
            "artifact_kind": (row.get("artifact") or {}).get("kind"),
            "relation": row.get("relation"),
        }
        for row in ledger.get("entries", ())
    ]


def structural_fingerprint(scenario: Scenario) -> str:
    """Hash topology and lifecycle shape while ignoring domain nouns and stable IDs."""
    hidden = scenario.hidden_world
    payload: dict[str, Any] = {
        "family": scenario.public.family,
        "events": _event_shape(scenario),
    }
    if scenario.public.family == "bitemporal_belief_revision":
        payload["ledger"] = _ledger_shape(hidden)
        payload["probe_axes"] = [
            (row["valid_at"], row["known_at"]) for row in hidden.get("temporal_probes", ())
        ]
    elif scenario.public.family == "recursive_investigation":
        nodes = hidden.get("derivation_dag", {}).get("nodes", ())
        kinds = {row["artifact_id"]: row["kind"] for row in nodes}
        payload["dag"] = sorted(
            (
                row["kind"],
                tuple(sorted(kinds[input_id] for input_id in row.get("input_ids", ()))),
                bool(row.get("required_for_reuse")),
            )
            for row in nodes
        )
        payload["depth"] = hidden.get("derivation_depth")
        payload["breadth"] = hidden.get("derivation_breadth")
    elif scenario.public.family == "decision_lineage":
        payload["ledger"] = _ledger_shape(hidden)
        payload["decision_context_count"] = len(hidden.get("decision_context_ids", ()))
    else:
        raise ValueError(f"unsupported cognitive-v2 family: {scenario.public.family}")
    return _digest(payload)


def causal_content_fingerprint(scenario: Scenario) -> str:
    """Hash causal values independently of public realization and event shape."""
    hidden = scenario.hidden_world
    payload: dict[str, Any] = {"family": scenario.public.family}
    if scenario.public.family == "bitemporal_belief_revision":
        ledger = hidden["world_ledger"]["entries"]
        payload["artifact_kinds"] = [
            (row.get("artifact") or {}).get("kind") for row in ledger if row.get("artifact")
        ]
        payload["valid_starts"] = [
            (row.get("artifact") or {}).get("valid_time", {}).get("start")
            for row in ledger
            if row.get("artifact")
        ]
        payload["belief_transitions"] = [
            (row["subject_key"], row["expected_value"])
            for row in hidden.get("temporal_probes", ())
        ]
        payload["difficulty_tier"] = hidden.get("difficulty_tier")
    else:
        incident = hidden["incident_world"]
        payload.update(
            {
                "root_service": incident["root_service"],
                "root_cause": incident["root_cause"],
                "correct_remediation": incident["correct_remediation"],
                "alert_service": incident["alert_service"],
                "dependencies": incident["dependencies"],
                "difficulty_tier": incident.get("difficulty_tier"),
            }
        )
        if scenario.public.family == "recursive_investigation":
            corrected = hidden.get("corrected_incident_world", {})
            payload["corrected_root_service"] = corrected.get("root_service")
            payload["corrected_root_cause"] = corrected.get("root_cause")
            payload["corrected_remediation"] = corrected.get("correct_remediation")
    return _digest(payload)


def world_fingerprint(scenario: Scenario) -> str:
    """Hash causal placement/topology together with the structural template."""
    return _digest(
        {
            "template": structural_fingerprint(scenario),
            "causal_content": causal_content_fingerprint(scenario),
        }
    )


def _internal_ids(scenario: Scenario) -> set[str]:
    ids = {row.memory_id for row in scenario.evaluator.durable}
    ids.update(scenario.evaluator.expected_retrieval_ids)
    hidden = scenario.hidden_world

    def visit(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                visit(child, child_key)
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                visit(child, key)
            return
        if not isinstance(value, str):
            return
        if key in {
            "artifact_id",
            "expected_artifact_id",
            "required_reuse_artifact_id",
            "decision_ref",
            "action_id",
            "outcome_id",
            "decision_context_ids",
            "late_evidence_ids",
            "invalidated_artifact_ids",
            "preserved_artifact_ids",
        }:
            ids.add(value)

    visit(hidden)
    return ids


def _answer_strings(expected: dict[str, Any]) -> Iterable[tuple[str, str]]:
    ignored = {"scope", "knowledge_state", "basis", "later_evidence_excluded"}
    for key, value in expected.items():
        if key in ignored:
            continue
        if isinstance(value, str) and len(value.strip()) >= 5:
            yield key, value


def validate_scenario_leakage(scenario: Scenario) -> dict[str, Any]:
    """Detect evaluator/control identifiers and direct answers exposed in checkpoint prompts."""
    event_text = "\n".join(event.content for event in scenario.public.events)
    leaked_ids = sorted(value for value in _internal_ids(scenario) if value in event_text)
    direct_answers: list[dict[str, str]] = []
    for event in scenario.public.events:
        if not event.evaluate:
            continue
        expected = scenario.evaluator.expected_answers.get(
            event.checkpoint_id or "",
            scenario.evaluator.expected_answer,
        )
        normalized_prompt = re.sub(r"\s+", " ", event.content.lower())
        for field, value in _answer_strings(expected):
            normalized_value = re.sub(r"\s+", " ", value.lower()).strip()
            if normalized_value in normalized_prompt:
                direct_answers.append(
                    {
                        "checkpoint_id": event.checkpoint_id or "",
                        "field": field,
                        "value": value,
                    }
                )
    return {
        "scenario_id": scenario.public.scenario_id,
        "leaked_internal_ids": leaked_ids,
        "direct_checkpoint_answers": direct_answers,
        "passed": not leaked_ids and not direct_answers,
    }


def validate_generator_validity(
    scenarios: list[Scenario],
    *,
    min_scenarios_per_family: int = 5,
    min_templates_per_family: int = 3,
    min_worlds_per_family: int = 5,
    min_difficulty_tiers_per_family: int = 3,
    min_unique_world_ratio: float = 0.8,
    max_template_share: float = 0.4,
    require_all_core_families: bool = True,
) -> dict[str, Any]:
    """Audit duplicate inflation, structural diversity, world diversity, and leakage."""
    if not scenarios:
        raise ValueError("at least one scenario is required")
    if min(
        min_scenarios_per_family,
        min_templates_per_family,
        min_worlds_per_family,
        min_difficulty_tiers_per_family,
    ) <= 0:
        raise ValueError("diversity thresholds must be positive")
    if not 0 < max_template_share <= 1 or not 0 < min_unique_world_ratio <= 1:
        raise ValueError("diversity ratios must be in (0, 1]")
    grouped: dict[str, list[Scenario]] = defaultdict(list)
    for scenario in scenarios:
        if scenario.public.family not in CORE_FAMILIES:
            raise ValueError(f"unsupported cognitive-v2 family: {scenario.public.family}")
        grouped[scenario.public.family].append(scenario)

    family_results: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    leakage_results = [validate_scenario_leakage(scenario) for scenario in scenarios]
    for family, rows in sorted(grouped.items()):
        templates = Counter(structural_fingerprint(row) for row in rows)
        worlds = Counter(world_fingerprint(row) for row in rows)
        public_hashes = Counter(row.public_hash() for row in rows)
        difficulty_tiers = Counter(
            str(row.hidden_world.get("difficulty_tier") or "unspecified") for row in rows
        )
        largest_template = max(templates.values())
        checks = {
            "scenario_count": len(rows) >= min_scenarios_per_family,
            "unique_public_scenarios": len(public_hashes) == len(rows),
            "structural_templates": len(templates) >= min_templates_per_family,
            "causal_worlds": len(worlds) >= min_worlds_per_family,
            "causal_world_ratio": len(worlds) / len(rows) >= min_unique_world_ratio,
            "template_concentration": largest_template / len(rows) <= max_template_share,
            "difficulty_strata": len(difficulty_tiers) >= min_difficulty_tiers_per_family,
        }
        family_results[family] = {
            "scenario_count": len(rows),
            "unique_public_hashes": len(public_hashes),
            "unique_structural_templates": len(templates),
            "unique_causal_worlds": len(worlds),
            "unique_causal_world_ratio": len(worlds) / len(rows),
            "largest_template_share": largest_template / len(rows),
            "template_counts": dict(sorted(templates.items())),
            "difficulty_tier_counts": dict(sorted(difficulty_tiers.items())),
            "checks": checks,
            "passed": all(checks.values()),
        }
        if not all(checks.values()):
            failures.append(
                {"family": family, "failed_checks": sorted(k for k, v in checks.items() if not v)}
            )
    missing_families = sorted(CORE_FAMILIES - set(grouped)) if require_all_core_families else []
    leakage_failures = [row for row in leakage_results if not row["passed"]]
    return {
        "schema_version": 2,
        "scenario_count": len(scenarios),
        "families": family_results,
        "thresholds": {
            "min_scenarios_per_family": min_scenarios_per_family,
            "min_templates_per_family": min_templates_per_family,
            "min_worlds_per_family": min_worlds_per_family,
            "min_difficulty_tiers_per_family": min_difficulty_tiers_per_family,
            "min_unique_world_ratio": min_unique_world_ratio,
            "max_template_share": max_template_share,
        },
        "missing_core_families": missing_families,
        "leakage": {
            "passed": not leakage_failures,
            "failures": leakage_failures,
        },
        "failures": failures,
        "passed": not failures and not missing_families and not leakage_failures,
    }
