from __future__ import annotations

import hashlib
import json
import os
import random
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..agents import (
    CognitiveAgentTrialExecutor,
    CognitiveVerticalSliceExecutor,
    DecisionLineageOracleExecutor,
    RecursiveInvestigationOracleExecutor,
    SYSTEM_PROMPTS,
)
from ..config import ROOT, load_config
from ..evaluators import (
    evaluate_cognitive_v2,
    evaluate_decision_lineage_v2,
    evaluate_outcome_v2,
    evaluate_recursive_v2,
)
from ..memory import OpenAIEmbeddingProvider
from ..providers import DeterministicProvider, OpenAICompatibleProvider
from ..reports import build_steering_report, render_steering_markdown
from ..scenarios.schema import Scenario, load_jsonl
from ..substrate import (
    AblatedSubstrateAdapter,
    ABLATION_SPECS,
    AblationFeature,
    CogneeRecordStore,
    DeterministicHashEmbeddingProvider,
    FlatSubstrateAdapter,
    HybridSubstrateAdapter,
    MappedJournalSubstrateAdapter,
    Mem0OSSRecordStore,
    MindGraphRecordStore,
    ReferenceSubstrateAdapter,
    SummarySubstrateAdapter,
    VectorSubstrateAdapter,
    ZepCloudRecordStore,
    ablation_manifest,
)
from ..substrate.conditions import COGNITIVE_V2_CONDITIONS
from ..telemetry import EventLog
from ..validation import audit_adapter_portability


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value


def _scenario_stratum(scenario: Scenario) -> dict[str, Any]:
    hidden = scenario.hidden_world
    incident = hidden.get("incident_world", {})
    metadata: dict[str, Any] = {
        "scenario_seed": scenario.public.seed,
        "scenario_variant": scenario.public.variant,
        "difficulty_tier": hidden.get("difficulty_tier")
        or incident.get("difficulty_tier", "unspecified"),
        "realization_pattern": hidden.get("realization_pattern")
        or incident.get("realization_pattern", "unspecified"),
    }
    if scenario.public.family == "recursive_investigation":
        metadata.update(
            {
                "derivation_depth": hidden["derivation_depth"],
                "derivation_breadth": hidden["derivation_breadth"],
                "premise_count": hidden["rederivability_control"]["premise_session_count"],
            }
        )
    elif scenario.public.family == "decision_lineage":
        metadata["decision_context_count"] = len(hidden["decision_context_ids"])
    elif scenario.public.family == "bitemporal_belief_revision":
        metadata["event_count"] = len(scenario.public.events)
    return metadata


class CognitiveV2Runner:
    """Balanced, manifest-producing runner for cognitive-v2 treatment cells."""

    def __init__(
        self,
        *,
        model: str = "deterministic-v1",
        conditions: list[str] | None = None,
        adapter: str = "reference",
        base_seed: int = 42,
        run_id: str | None = None,
        results_root: Path | None = None,
        provider_base_url: str | None = None,
        retrieval_k: int = 8,
        retrieval_tokens: int = 1200,
        operating_mode: str = "matched-budget",
        scaffold_version: str = "canonical-v1",
        ablation: str | None = None,
    ) -> None:
        self.conditions = conditions or list(COGNITIVE_V2_CONDITIONS)
        unknown = set(self.conditions) - set(COGNITIVE_V2_CONDITIONS)
        if unknown:
            raise ValueError(f"unknown cognitive-v2 conditions: {sorted(unknown)}")
        if adapter not in {
            "reference",
            "flat",
            "summary",
            "vector",
            "hybrid",
            "mindgraph-v2",
            "mem0-oss",
            "zep-cloud",
            "cognee",
        }:
            raise ValueError(f"unknown cognitive-v2 adapter: {adapter}")
        self.model = model
        self.adapter_name = adapter
        self.base_seed = base_seed
        self.provider_base_url = provider_base_url
        if retrieval_k <= 0 or retrieval_tokens <= 0:
            raise ValueError("retrieval_k and retrieval_tokens must be positive")
        if operating_mode not in {"matched-budget", "natural"}:
            raise ValueError(f"unknown operating mode: {operating_mode}")
        if scaffold_version not in SYSTEM_PROMPTS:
            raise ValueError(f"unknown scaffold version: {scaffold_version}")
        self.retrieval_k = retrieval_k
        self.retrieval_tokens = retrieval_tokens
        self.operating_mode = operating_mode
        self.scaffold_version = scaffold_version
        self.ablation = AblationFeature(ablation) if ablation else None
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-cognitive-v2")
        self.results_root = results_root or ROOT / "results"
        self.raw_path = self.results_root / "raw" / f"{self.run_id}.jsonl"
        self.evaluated_path = self.results_root / "evaluated" / f"{self.run_id}.jsonl"
        self.trace_path = self.results_root / "traces" / f"{self.run_id}.jsonl"
        self.manifest_path = self.results_root / "raw" / f"{self.run_id}.manifest.json"
        self.steering_path = self.results_root / "aggregated" / f"{self.run_id}-steering.json"
        self.steering_markdown_path = (
            self.results_root / "aggregated" / f"{self.run_id}-steering.md"
        )

    def _provider(self) -> tuple[Any, str]:
        if self.model == "deterministic-v1":
            return DeterministicProvider(), "deterministic"
        models = load_config("models.yaml")
        config = models.get(self.model, {})
        model_id = str(config.get("model", self.model))
        base = self.provider_base_url or os.getenv("PROVIDER_BASE_URL")
        key = os.getenv("OPENROUTER_API_KEY") or os.getenv("PROVIDER_API_KEY") or os.getenv(
            "OPENAI_API_KEY"
        )
        if os.getenv("OPENROUTER_API_KEY") and not base:
            base = "https://openrouter.ai/api/v1"
        if not base or not key:
            raise RuntimeError("real model requires a provider base URL and API key")
        return OpenAICompatibleProvider(model_id, base, key), "openai-compatible"

    def _base_adapter(self):
        if self.adapter_name == "reference":
            return ReferenceSubstrateAdapter()
        if self.adapter_name == "flat":
            return FlatSubstrateAdapter()
        if self.adapter_name == "summary":
            return SummarySubstrateAdapter(summary_tokens=self.retrieval_tokens)
        if self.adapter_name == "vector":
            return VectorSubstrateAdapter(self._embedding_provider())
        if self.adapter_name == "hybrid":
            return HybridSubstrateAdapter(self._embedding_provider())
        if self.adapter_name == "mindgraph-v2":
            return MappedJournalSubstrateAdapter(
                MindGraphRecordStore(
                    os.getenv("MINDGRAPH_BASE_URL", "http://127.0.0.1:18790"),
                    api_key=os.getenv("MINDGRAPH_API_KEY"),
                )
            )
        if self.adapter_name == "mem0-oss":
            return MappedJournalSubstrateAdapter(
                Mem0OSSRecordStore(
                    os.getenv("MEM0_BASE_URL", "http://127.0.0.1:8000"),
                    api_key=os.getenv("MEM0_API_KEY"),
                )
            )
        if self.adapter_name == "cognee":
            return MappedJournalSubstrateAdapter(
                CogneeRecordStore(
                    os.getenv("COGNEE_BASE_URL", "http://127.0.0.1:8000"),
                    api_key=os.getenv("COGNEE_API_KEY"),
                )
            )
        api_key = os.getenv("ZEP_API_KEY")
        if not api_key:
            raise RuntimeError("zep-cloud adapter requires ZEP_API_KEY")
        return MappedJournalSubstrateAdapter(
            ZepCloudRecordStore(
                api_key,
                base_url=os.getenv("ZEP_API_URL", "https://api.getzep.com"),
            )
        )

    def _adapter(self):
        adapter = self._base_adapter()
        if self.ablation is not None:
            return AblatedSubstrateAdapter(adapter, self.ablation)
        return adapter

    def _disabled_tools(self) -> set[str]:
        if self.ablation is AblationFeature.NO_ACTIVE_RETRIEVAL:
            return {"substrate_retrieve"}
        if self.ablation is AblationFeature.NO_AUDIT_RECEIPT:
            return {"substrate_audit"}
        return set()

    def _ablation_status(self, scenario: Scenario, condition_id: str) -> str:
        if self.ablation is None:
            return "none"
        if condition_id == "oracle-passive" or condition_id in {
            "stateless",
            "transcript",
            "transcript-full",
        }:
            return "unablated-control"
        spec = ABLATION_SPECS[self.ablation]
        if condition_id not in spec.opportunity_conditions:
            return "no-condition-opportunity"
        if scenario.public.family not in spec.opportunity_families:
            return "no-scenario-opportunity"
        return "applied"

    def _embedding_provider(self):
        if self.model == "deterministic-v1":
            return DeterministicHashEmbeddingProvider()
        api_key = os.getenv("COGMEMBENCH_EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "vector and hybrid baselines require COGMEMBENCH_EMBEDDING_API_KEY "
                "or OPENAI_API_KEY for non-deterministic runs"
            )
        return OpenAIEmbeddingProvider(
            api_key,
            model=os.getenv("COGMEMBENCH_EMBEDDING_MODEL", "text-embedding-3-small"),
            base_url=os.getenv("COGMEMBENCH_EMBEDDING_BASE_URL", "https://api.openai.com/v1"),
        )

    def _schedule(self, scenarios: list[Scenario]) -> list[tuple[Scenario, str]]:
        ordered = list(scenarios)
        random.Random(self.base_seed).shuffle(ordered)
        schedule = []
        for index, scenario in enumerate(ordered):
            offset = index % len(self.conditions)
            rotated = self.conditions[offset:] + self.conditions[:offset]
            schedule.extend((scenario, condition) for condition in rotated)
        return schedule

    def _oracle(self, scenario: Scenario) -> tuple[dict[str, Any], dict[str, Any]]:
        adapter = self._base_adapter()
        family = scenario.public.family
        if family == "bitemporal_belief_revision":
            trial = CognitiveVerticalSliceExecutor(adapter).run(scenario)
            evaluation = evaluate_cognitive_v2(trial, scenario)
        elif family == "recursive_investigation":
            trial = RecursiveInvestigationOracleExecutor(adapter).run(scenario)
            evaluation = evaluate_recursive_v2(trial, scenario)
        elif family == "decision_lineage":
            trial = DecisionLineageOracleExecutor(adapter).run(scenario)
            evaluation = evaluate_decision_lineage_v2(trial, scenario)
        else:
            raise ValueError(f"unsupported cognitive-v2 family: {family}")
        trial["condition"] = "oracle-passive"
        trial.setdefault("capabilities", asdict(adapter.capability_manifest()))
        return trial, evaluation

    def run(self, scenario_path: Path) -> dict[str, Any]:
        scenarios = load_jsonl(scenario_path)
        if not scenarios or any(row.public.schema_version != 2 for row in scenarios):
            raise ValueError("cognitive-v2 runner requires a non-empty schema-v2 suite")
        for path in (
            self.raw_path,
            self.evaluated_path,
            self.trace_path,
            self.manifest_path,
            self.steering_path,
            self.steering_markdown_path,
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.raw_path.unlink(missing_ok=True)
        self.evaluated_path.unlink(missing_ok=True)
        self.trace_path.unlink(missing_ok=True)
        provider, provider_name = self._provider()
        trace = EventLog(self.trace_path)
        schedule = self._schedule(scenarios)
        portability_audit = None
        if self.adapter_name != "reference":
            portability_audit = audit_adapter_portability(self._base_adapter())
            if not portability_audit["passed"]:
                raise RuntimeError(
                    "external adapter portability preflight failed: "
                    + json.dumps(portability_audit, sort_keys=True, default=str)
                )
        manifest = {
            "run_id": self.run_id,
            "protocol": "cognitive-v2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scenario_file": str(scenario_path.resolve()),
            "scenario_sha256": hashlib.sha256(scenario_path.read_bytes()).hexdigest(),
            "scenario_count": len(scenarios),
            "trial_count": len(schedule),
            "difficulty_tier_counts": dict(
                sorted(Counter(_scenario_stratum(row)["difficulty_tier"] for row in scenarios).items())
            ),
            "realization_pattern_counts": dict(
                sorted(
                    Counter(
                        _scenario_stratum(row)["realization_pattern"] for row in scenarios
                    ).items()
                )
            ),
            "model": self.model,
            "repetition": self.base_seed,
            "provider": provider_name,
            "adapter": self.adapter_name,
            "operating_mode": self.operating_mode,
            "scaffold": {
                "version": self.scaffold_version,
                "sha256": hashlib.sha256(
                    SYSTEM_PROMPTS[self.scaffold_version].encode()
                ).hexdigest(),
            },
            "ablation": (
                ablation_manifest(self.ablation) if self.ablation is not None else None
            ),
            "conditions": self.conditions,
            "condition_contracts": {
                key: _jsonable(value) for key, value in COGNITIVE_V2_CONDITIONS.items()
                if key in self.conditions
            },
            "budgets": {
                "retrieval_max_items": self.retrieval_k,
                "matched_context_tokens": self.retrieval_tokens,
                "full_transcript_tokens": None,
                "checkpoint_overrides": "scenario-declared",
            },
            "schedule_sha256": hashlib.sha256(
                json.dumps(
                    [(row.public.scenario_id, condition) for row, condition in schedule],
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
            "adapter_manifest": _jsonable(self._adapter().capability_manifest()),
            "portability_audit": _jsonable(portability_audit),
            "condition_backends": {
                condition: (
                    "none"
                    if condition in {"stateless", "transcript", "transcript-full"}
                    else self.adapter_name
                )
                for condition in self.conditions
            },
        }
        self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        evaluated_rows = []
        for scenario, condition_id in schedule:
            trial_id = hashlib.sha256(
                f"{scenario.public.scenario_id}\0{condition_id}\0{self.model}\0"
                f"{self.adapter_name}\0{self.ablation.value if self.ablation else 'none'}".encode()
            ).hexdigest()[:24]
            try:
                if condition_id == "oracle-passive":
                    trial, evaluation = self._oracle(scenario)
                else:
                    condition = COGNITIVE_V2_CONDITIONS[condition_id]
                    adapter = self._adapter() if condition.persistent else None
                    trial = CognitiveAgentTrialExecutor(
                        provider,
                        condition,
                        trace,
                        adapter=adapter,
                        retrieval_k=self.retrieval_k,
                        retrieval_tokens=self.retrieval_tokens,
                        transcript_tokens=self.retrieval_tokens,
                        scaffold_version=self.scaffold_version,
                        disabled_tools=(
                            self._disabled_tools()
                            if self._ablation_status(scenario, condition_id) == "applied"
                            else set()
                        ),
                    ).run(scenario)
                    evaluation = evaluate_outcome_v2(trial, scenario)
                trial.update(
                    {
                        "trial_id": trial_id,
                        "model": self.model,
                        "repetition": self.base_seed,
                        "provider": provider_name,
                        "backend": (
                            "none"
                            if condition_id in {"stateless", "transcript", "transcript-full"}
                            else self.adapter_name
                        ),
                        "scenario_public_hash": scenario.public_hash(),
                        "ablation": self.ablation.value if self.ablation is not None else None,
                        "ablation_status": self._ablation_status(scenario, condition_id),
                        "ablation_applied": self._ablation_status(scenario, condition_id)
                        == "applied",
                        **_scenario_stratum(scenario),
                        "valid": True,
                        "error": None,
                    }
                )
            except Exception as exc:
                trial = {
                    "trial_id": trial_id,
                    "scenario_id": scenario.public.scenario_id,
                    "family": scenario.public.family,
                    "condition": condition_id,
                    "model": self.model,
                    "repetition": self.base_seed,
                    "provider": provider_name,
                    "backend": self.adapter_name,
                    "scenario_public_hash": scenario.public_hash(),
                    "ablation": self.ablation.value if self.ablation is not None else None,
                    "ablation_status": self._ablation_status(scenario, condition_id),
                    "ablation_applied": self._ablation_status(scenario, condition_id) == "applied",
                    **_scenario_stratum(scenario),
                    "valid": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                evaluation = {"metrics": {}, "checks": {}}
            raw = _jsonable(trial)
            evaluated = {**raw, "evaluation": _jsonable(evaluation)}
            with self.raw_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(raw, sort_keys=True) + "\n")
            with self.evaluated_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(evaluated, sort_keys=True) + "\n")
            evaluated_rows.append(evaluated)

        steering = build_steering_report(evaluated_rows)
        self.steering_path.write_text(json.dumps(steering, indent=2, sort_keys=True) + "\n")
        self.steering_markdown_path.write_text(render_steering_markdown(steering))
        manifest.update(
            {
                "completed_trials": sum(row["valid"] for row in evaluated_rows),
                "invalid_trials": sum(not row["valid"] for row in evaluated_rows),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "artifacts": {
                    "raw": str(self.raw_path),
                    "evaluated": str(self.evaluated_path),
                    "trace": str(self.trace_path),
                    "steering_json": str(self.steering_path),
                    "steering_markdown": str(self.steering_markdown_path),
                },
            }
        )
        self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return manifest
