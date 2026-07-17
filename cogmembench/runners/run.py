from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import subprocess
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..agents import (
    CONDITIONS,
    DevelopmentV2TrialExecutor,
    OracleTrialExecutor,
    TrialExecutor,
)
from ..config import ROOT, load_config
from ..evaluators import evaluate_trial, evaluate_trial_v2
from ..memory import (
    MindGraphHTTPMemory,
    MindGraphMCPMemory,
    OpenAIEmbeddingProvider,
    ReferenceCognitiveMemory,
)
from ..memory.reset import contamination_test
from ..providers import DeterministicProvider, OpenAICompatibleProvider
from ..protocol import verify_protocol_lock
from ..scenarios.schema import Scenario, load_jsonl
from ..telemetry import EventLog, TraceEvent
from .locks import ExclusiveRunLock


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_sha(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _repo_state(path: Path) -> dict[str, Any]:
    """Record a commit plus hashes of any local overlay without storing patch contents."""
    sha = _repo_sha(path)
    if sha is None:
        return {"sha": None, "dirty": None, "status_sha256": None, "diff_sha256": None}
    try:
        status = subprocess.check_output(
            ["git", "-C", str(path), "status", "--porcelain=v1", "--untracked-files=normal"],
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        diff = subprocess.check_output(
            ["git", "-C", str(path), "diff", "--binary", "HEAD", "--"],
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return {"sha": sha, "dirty": None, "status_sha256": None, "diff_sha256": None}
    return {
        "sha": sha,
        "dirty": bool(status),
        "status_sha256": hashlib.sha256(status).hexdigest() if status else None,
        "diff_sha256": hashlib.sha256(diff).hexdigest() if diff else None,
    }


class BenchmarkRunner:
    def __init__(
        self,
        *,
        scale: str,
        model: str,
        conditions: list[str],
        backend: str,
        base_seed: int,
        provider_base_url: str | None = None,
        resume: bool = False,
        run_id: str | None = None,
        results_root: Path | None = None,
        protocol_lock: str | None = None,
        capture_repository_state: bool | None = None,
    ):
        unknown = set(conditions) - set(CONDITIONS)
        if unknown:
            raise ValueError(f"unknown conditions: {sorted(unknown)}")
        self.scale = scale
        models = load_config("models.yaml")
        self.model_label = model
        if model in models:
            self.model_config = models[model]
        else:
            self.model_config = next(
                (config for config in models.values() if config.get("model") == model),
                {"model": model, "temperature": 0, "max_output_tokens": 1024},
            )
        self.model = str(self.model_config.get("model", model))
        self.conditions = conditions
        self.backend = backend
        self.base_seed = base_seed
        self.provider_base_url = provider_base_url
        self.resume = resume
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{scale}"
        self.results_root = results_root or ROOT / "results"
        self.protocol_lock = protocol_lock
        self.capture_repository_state = (
            results_root is None
            if capture_repository_state is None
            else capture_repository_state
        )
        self.raw_path = self.results_root / "raw" / f"{self.run_id}.jsonl"
        self.trace_path = self.results_root / "traces" / f"{self.run_id}.jsonl"
        self.manifest_path = self.results_root / "raw" / f"{self.run_id}.manifest.json"
        self.raw_path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._verified_protocol: dict[str, Any] | None = None

    def _provider(self):
        if self.model == "deterministic-v1":
            return DeterministicProvider(), "deterministic"
        base = self.provider_base_url or os.getenv("PROVIDER_BASE_URL")
        key = os.getenv("OPENROUTER_API_KEY") or os.getenv("PROVIDER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if os.getenv("OPENROUTER_API_KEY") and not base:
            base = "https://openrouter.ai/api/v1"
        if not base or not key:
            raise RuntimeError("real model requires OPENROUTER_API_KEY or provider base URL and API key")
        openrouter = "openrouter.ai" in base
        configured_provider = self.model_config.get("provider_only")
        provider = None
        if openrouter and configured_provider:
            only = (
                [item.strip() for item in configured_provider.split(",") if item.strip()]
                if isinstance(configured_provider, str)
                else list(configured_provider)
            )
            provider = {
                "only": only,
                "allow_fallbacks": False,
                "require_parameters": True,
            }
        client = OpenAICompatibleProvider(
            self.model,
            base,
            key,
            timeout=float(os.getenv("COGMEMBENCH_PROVIDER_TIMEOUT_SECONDS", "180")),
            provider_preferences=provider,
            disable_reasoning=openrouter,
            omit_temperature=bool(self.model_config.get("omit_temperature", False)),
        )
        return client, "openrouter" if openrouter else "openai-compatible"

    def _memory(self, condition: str, trace: EventLog):
        if not condition.startswith("mindgraph-") and condition != "oracle-policy":
            return None
        if self.backend == "reference":
            return ReferenceCognitiveMemory()
        base = os.getenv("MINDGRAPH_BASE_URL", "http://127.0.0.1:18790")
        memory_type = (
            MindGraphMCPMemory
            if self._executor_version == "development-v2" and condition.startswith("mindgraph-active")
            else MindGraphHTTPMemory
        )
        return memory_type(
            base,
            api_key=os.getenv("MINDGRAPH_API_KEY"),
            backend_label=self.backend,
            timeout=float(os.getenv("COGMEMBENCH_MINDGRAPH_TIMEOUT_SECONDS", "300")),
            trace=lambda payload: trace.emit(
                TraceEvent(
                    "mindgraph_http",
                    "",
                    condition,
                    duration_ms=payload.get("duration_ms"),
                    payload=payload,
                )
            ),
        )

    def _embedding_provider(self) -> OpenAIEmbeddingProvider:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("flat-hybrid requires OPENAI_API_KEY")
        return OpenAIEmbeddingProvider(
            key,
            model=os.getenv("MINDGRAPH_EMBEDDING_MODEL", "text-embedding-3-small"),
            base_url=os.getenv("COGMEMBENCH_EMBEDDING_BASE_URL", "https://api.openai.com/v1"),
            timeout=float(os.getenv("COGMEMBENCH_EMBEDDING_TIMEOUT_SECONDS", "120")),
            cost_per_million_tokens=float(
                os.getenv("COGMEMBENCH_EMBEDDING_COST_PER_MILLION", "0.02")
            ),
        )

    @property
    def _executor_version(self) -> str:
        return str((self._verified_protocol or {}).get("executor_version", "v1"))

    def run(self, scenario_path: Path) -> dict[str, Any]:
        self._verified_protocol = (
            verify_protocol_lock(self.protocol_lock) if self.protocol_lock else None
        )
        with ExitStack() as stack:
            stack.enter_context(
                ExclusiveRunLock(self.results_root / "locks" / f"run-{self.run_id}.lock")
            )
            if self.backend in {"mindgraph-local", "mindgraph-cloud"}:
                stack.enter_context(
                    ExclusiveRunLock(self.results_root / "locks" / f"backend-{self.backend}.lock")
                )
            return self._run_locked(scenario_path)

    def _run_locked(self, scenario_path: Path) -> dict[str, Any]:
        protocol = self._verified_protocol
        scenarios = load_jsonl(scenario_path)
        completed: set[str] = set()
        if not self.resume:
            self.raw_path.unlink(missing_ok=True)
            self.trace_path.unlink(missing_ok=True)
        if self.resume and self.raw_path.exists():
            with self.raw_path.open() as fh:
                completed = {
                    row["trial_id"]
                    for line in fh
                    if line.strip()
                    for row in [json.loads(line)]
                    if row.get("valid")
                }
        trace = EventLog(self.trace_path)
        provider, provider_name = self._provider()
        isolation: dict[str, Any] = {}
        for condition in self.conditions:
            memory = self._memory(condition, trace)
            if memory is not None:
                isolation = contamination_test(memory)
                if not isolation["passed"]:
                    raise RuntimeError(f"backend contamination test failed: {isolation}")
                diagnostic = isolation.get("retrieval_diagnostic", {})
                if (
                    self.backend == "mindgraph-local"
                    and os.getenv("OPENAI_API_KEY")
                    and not diagnostic.get("hybrid_verified")
                ):
                    raise RuntimeError(
                        "OPENAI_API_KEY is configured but hybrid retrieval did not expose both "
                        f"fts and vec legs: {diagnostic}"
                    )
                if hasattr(memory, "close"):
                    memory.close()
                break
        schedule = self._schedule(scenarios)
        manifest = self._manifest(scenario_path, scenarios, provider_name, isolation)
        manifest["protocol_lock"] = protocol
        manifest["schedule"] = {
            "version": (protocol or {}).get("schedule_version", "fixed-v1"),
            "sha256": hashlib.sha256(
                json.dumps(
                    [(scenario.public.scenario_id, condition) for scenario, condition in schedule],
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
            "trials": len(schedule),
        }
        if self.resume and self.manifest_path.exists():
            previous = json.loads(self.manifest_path.read_text())
            self._verify_resume_compatibility(previous, manifest)
            manifest["generated_at"] = previous.get("generated_at", manifest["generated_at"])
            manifest["resume_count"] = int(previous.get("resume_count", 0)) + 1
        self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        for scenario, condition in schedule:
            trial_id = hashlib.sha256(
                f"{scenario.public.scenario_id}\0{condition}\0{self.model}\0{self.backend}".encode()
            ).hexdigest()[:24]
            if trial_id in completed:
                continue
            start_index = len(trace.events)
            memory = self._memory(condition, trace)
            executor_type = (
                OracleTrialExecutor
                if condition == "oracle-policy"
                else (
                    DevelopmentV2TrialExecutor
                    if self._executor_version == "development-v2"
                    else TrialExecutor
                )
            )
            executor_kwargs = {
                "memory": memory,
                "embedding_provider": (
                    self._embedding_provider() if condition == "flat-hybrid" else None
                ),
                "retrieval_k": int(load_config("scales.yaml")[self.scale]["retrieval_k"]),
                "temperature": float(self.model_config.get("temperature", 0)),
                "max_output_tokens": int(self.model_config.get("max_output_tokens", 1024)),
                "input_cost_per_million": float(
                    self.model_config.get("input_cost_per_million", 0)
                ),
                "output_cost_per_million": float(
                    self.model_config.get("output_cost_per_million", 0)
                ),
            }
            executor = (
                executor_type(provider, trace, **executor_kwargs)
                if condition == "oracle-policy"
                else executor_type(provider, condition, trace, **executor_kwargs)
            )
            started = time.time()
            try:
                row = (
                    executor.run(scenario)
                    if condition == "oracle-policy"
                    else executor.run(scenario.public)
                )
                row["valid"] = True
                row["error"] = None
            except Exception as exc:
                row = {
                    "scenario_id": scenario.public.scenario_id,
                    "family": scenario.public.family,
                    "seed": scenario.public.seed,
                    "variant": scenario.public.variant,
                    "condition": condition,
                    "answer": "",
                    "metrics": executor.metrics,
                    "memory_snapshot": {},
                    "valid": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            if memory is not None and hasattr(memory, "provider_telemetry"):
                provider_telemetry = memory.provider_telemetry()
                row.setdefault("metrics", {}).update(provider_telemetry["metrics"])
                row["mindgraph_provider_telemetry"] = provider_telemetry
            if memory is not None and hasattr(memory, "close"):
                memory.close()
            self._finalize_efficiency_metrics(row)
            row["trial_id"] = trial_id
            row["model"] = self.model
            row["provider"] = provider_name
            row["backend"] = (
                self.backend
                if condition.startswith("mindgraph") or condition == "oracle-policy"
                else (
                    "flat-hybrid"
                    if condition == "flat-hybrid"
                    else ("flat-bm25" if condition == "flat" else "none")
                )
            )
            row["scenario_public_hash"] = scenario.public_hash()
            row["wall_seconds"] = time.time() - started
            row_events = trace.events[start_index:]
            row["evaluation"] = (
                (
                    evaluate_trial_v2(row, scenario, row_events)
                    if (protocol or {}).get("evaluator_version") == "development-v2"
                    else evaluate_trial(row, scenario, row_events)
                )
                if row["valid"]
                else {"metrics": {}, "checks": {}}
            )
            with self.raw_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
            if row["valid"]:
                completed.add(trial_id)
        manifest["completed_trials"] = len(completed)
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        (self.results_root / "LATEST").write_text(self.run_id)
        return manifest

    def _schedule(self, scenarios: list[Scenario]) -> list[tuple[Scenario, str]]:
        version = str((self._verified_protocol or {}).get("schedule_version", "fixed-v1"))
        if version != "balanced-v2":
            return [(scenario, condition) for scenario in scenarios for condition in self.conditions]
        ordered = list(scenarios)
        random.Random(self.base_seed).shuffle(ordered)
        schedule: list[tuple[Scenario, str]] = []
        for index, scenario in enumerate(ordered):
            offset = index % len(self.conditions)
            rotated = self.conditions[offset:] + self.conditions[:offset]
            schedule.extend((scenario, condition) for condition in rotated)
        return schedule

    @staticmethod
    def _verify_resume_compatibility(
        previous: dict[str, Any], current: dict[str, Any]
    ) -> None:
        stable_fields = (
            "scale",
            "base_seed",
            "model",
            "model_config",
            "provider",
            "backend",
            "conditions",
            "scenario_sha256",
            "retrieval_configuration",
            "server_treatment_controls",
            "protocol_lock",
            "schedule",
        )
        mismatches = {
            field: {"previous": previous.get(field), "current": current.get(field)}
            for field in stable_fields
            if previous.get(field) != current.get(field)
        }
        if mismatches:
            raise RuntimeError(
                "resume treatment mismatch: " + json.dumps(mismatches, sort_keys=True)
            )

    @staticmethod
    def _finalize_efficiency_metrics(row: dict[str, Any]) -> None:
        metrics = row.setdefault("metrics", {})
        agent_total = metrics.get("agent_total_tokens")
        if agent_total is None:
            agent_total = (metrics.get("input_tokens") or 0) + (
                metrics.get("output_tokens") or 0
            )
            metrics["agent_total_tokens"] = agent_total
        read_context = metrics.get("read_context_tokens")
        if read_context is None:
            read_context = (metrics.get("historical_context_tokens") or 0) + (
                metrics.get("retrieved_context_tokens") or 0
            )
            metrics["read_context_tokens"] = read_context
        construction = metrics.get("mindgraph_extraction_total_tokens")
        if construction is None:
            construction = metrics.get("embedding_input_tokens") or 0
        metrics["memory_construction_tokens"] = construction
        metrics["lifecycle_tokens"] = agent_total + construction

    def _manifest(self, scenario_path: Path, scenarios: list[Scenario], provider: str, isolation: dict[str, Any]) -> dict[str, Any]:
        workspace = ROOT.parent
        repos = ["mindgraph-rs", "mindgraph-py", "mindgraph-ts", "mindgraph-mcp", "mindgraph-hermes", "mindgraph-cloud", "mnestic", "mnestic-benchmarks", "mindgraph-benchmarks"]
        return {
            "run_id": self.run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scale": self.scale,
            "base_seed": self.base_seed,
            "model": self.model,
            "model_config": self.model_config,
            "provider": provider,
            "backend": self.backend,
            "conditions": self.conditions,
            "scenario_count": len(scenarios),
            "scenario_file": str(scenario_path),
            "scenario_sha256": _sha(scenario_path),
            "token_accounting": "provider" if provider != "deterministic" else "deterministic-fallback",
            "retrieval_configuration": {
                "top_k": int(load_config("scales.yaml")[self.scale]["retrieval_k"]),
                "flat_bm25": "okapi-bm25",
                "flat_hybrid_fusion": "rrf-k60" if "flat-hybrid" in self.conditions else None,
                "mindgraph_context_endpoint": "/retrieve/context",
                "mindgraph_retrieval_mode": (
                    "hybrid-if-embeddings-available"
                    if any(
                        condition.startswith("mindgraph-") or condition == "oracle-policy"
                        for condition in self.conditions
                    )
                    else None
                ),
                "embedding_provider": "openai" if os.getenv("OPENAI_API_KEY") else None,
                "embedding_model": (
                    os.getenv("MINDGRAPH_EMBEDDING_MODEL", "text-embedding-3-small")
                    if os.getenv("OPENAI_API_KEY")
                    else None
                ),
            },
            "server_treatment_controls": {
                "wiki_autocompile": os.getenv("MINDGRAPH_WIKI_AUTOCOMPILE"),
                "llm_base_url": os.getenv("MINDGRAPH_LLM_BASE_URL"),
                "llm_model": os.getenv("MINDGRAPH_LLM_MODEL"),
                "binary_sha256": os.getenv("MINDGRAPH_SERVER_BINARY_SHA256"),
                "source_sha": os.getenv("MINDGRAPH_SERVER_SOURCE_SHA"),
            },
            "environment": {"python": platform.python_version(), "platform": platform.platform()},
            "repository_shas": (
                {repo: _repo_sha(workspace / repo) for repo in repos}
                if self.capture_repository_state
                else {}
            ),
            "repository_states": (
                {
                    "workspace": _repo_state(workspace),
                    **{repo: _repo_state(workspace / repo) for repo in repos},
                }
                if self.capture_repository_state
                else {}
            ),
            "config_hashes": {name: _sha(ROOT / "configs" / name) for name in ("models.yaml", "conditions.yaml", "scales.yaml", "metrics.yaml")},
            "isolation_test": isolation,
        }
