from __future__ import annotations

import json

import pytest

from cogmembench.providers import DeterministicProvider
from cogmembench.runners import BenchmarkRunner
from cogmembench.runners.run import _repo_state
from cogmembench.runners.locks import ExclusiveRunLock
from cogmembench.protocol import verify_protocol_lock
from cogmembench.scenarios.generators import generate_development_v2, generate_suite
from cogmembench.scenarios.schema import save_jsonl


def test_checkpoint_resume_does_not_duplicate_trials(tmp_path, monkeypatch):
    scenarios = generate_suite("smoke", 7, 1, [42], 8)[:1]
    path = tmp_path / "one.jsonl"
    save_jsonl(path, scenarios)
    run_id = "pytest-resume"
    results = tmp_path / "results"
    runner = BenchmarkRunner(scale="smoke", model="deterministic-v1", conditions=["stateless", "flat"], backend="reference", base_seed=7, run_id=run_id, results_root=results)
    runner.run(path)
    raw = results / "raw" / f"{run_id}.jsonl"
    before = raw.read_text().splitlines()
    BenchmarkRunner(scale="smoke", model="deterministic-v1", conditions=["stateless", "flat"], backend="reference", base_seed=7, run_id=run_id, resume=True, results_root=results).run(path)
    after = raw.read_text().splitlines()
    assert len(before) == len(after) == 2


def test_provider_failure_is_preserved_per_trial(tmp_path, monkeypatch):
    class FailProvider:
        model_id = "fail"

        def complete(self, *args, **kwargs):
            raise RuntimeError("synthetic provider outage")

    scenarios = generate_suite("smoke", 8, 1, [42], 8)[:1]
    path = tmp_path / "failure.jsonl"
    save_jsonl(path, scenarios)
    results = tmp_path / "results"
    runner = BenchmarkRunner(scale="smoke", model="deterministic-v1", conditions=["stateless"], backend="reference", base_seed=8, run_id="pytest-failure", results_root=results)
    monkeypatch.setattr(runner, "_provider", lambda: (FailProvider(), "test-failure"))
    runner.run(path)
    raw = results / "raw" / "pytest-failure.jsonl"
    row = json.loads(raw.read_text().splitlines()[-1])
    assert not row["valid"]
    assert "synthetic provider outage" in row["error"]

    recovered = BenchmarkRunner(
        scale="smoke",
        model="deterministic-v1",
        conditions=["stateless"],
        backend="reference",
        base_seed=8,
        run_id="pytest-failure",
        resume=True,
        results_root=results,
    )
    monkeypatch.setattr(
        recovered, "_provider", lambda: (DeterministicProvider(), "test-failure")
    )
    recovered.run(path)
    attempts = [json.loads(line) for line in raw.read_text().splitlines()]
    assert len(attempts) == 2
    assert attempts[-1]["valid"]


def test_resume_rejects_changed_treatment(tmp_path):
    scenarios = generate_suite("smoke", 9, 1, [42], 8)[:1]
    path = tmp_path / "resume.jsonl"
    save_jsonl(path, scenarios)
    results = tmp_path / "results"
    BenchmarkRunner(
        scale="smoke",
        model="deterministic-v1",
        conditions=["stateless"],
        backend="reference",
        base_seed=9,
        run_id="resume-mismatch",
        results_root=results,
    ).run(path)

    changed = BenchmarkRunner(
        scale="smoke",
        model="deterministic-v1",
        conditions=["stateless", "flat"],
        backend="reference",
        base_seed=9,
        run_id="resume-mismatch",
        resume=True,
        results_root=results,
    )
    with pytest.raises(RuntimeError, match="resume treatment mismatch"):
        changed.run(path)


def test_strong_model_pins_openrouter_provider(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    runner = BenchmarkRunner(
        scale="smoke",
        model="strong-model",
        conditions=["stateless"],
        backend="reference",
        base_seed=42,
    )
    provider, provider_name = runner._provider()
    assert provider_name == "openrouter"
    assert provider.model_id == "openai/gpt-5.4-mini"
    assert provider.provider_preferences == {
        "only": ["openai"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }


def test_repo_state_handles_non_repository(tmp_path):
    assert _repo_state(tmp_path) == {
        "sha": None,
        "dirty": None,
        "status_sha256": None,
        "diff_sha256": None,
    }


def test_frozen_smoke_protocol_verifies():
    verified = verify_protocol_lock("smoke-v1")
    assert verified["protocol_id"] == "smoke-v1"
    assert verified["verified_files"] == 7


def test_frozen_development_mvp_protocol_verifies():
    verified = verify_protocol_lock("development-mvp-v1")
    assert verified["protocol_id"] == "development-mvp-v1"
    assert verified["verified_files"] == 7


def test_frozen_development_v2_protocol_verifies():
    verified = verify_protocol_lock("development-mvp-v2")
    assert verified["protocol_id"] == "development-mvp-v2"
    assert verified["executor_version"] == "development-v2"
    assert verified["evaluator_version"] == "development-v2"
    assert verified["schedule_version"] == "balanced-v2"
    assert verified["locked_files"] == 16
    assert verified["verified_local_files"] == 13
    assert verified["verified_files"] + len(verified["unavailable_external_files"]) == 16


def test_backend_lock_rejects_concurrent_owner(tmp_path):
    path = tmp_path / "backend.lock"
    with ExclusiveRunLock(path):
        with pytest.raises(RuntimeError, match="is held"):
            with ExclusiveRunLock(path):
                pass


def test_balanced_v2_schedule_rotates_every_condition_through_every_position():
    runner = BenchmarkRunner(
        scale="development",
        model="deterministic-v1",
        conditions=["stateless", "transcript", "flat", "mindgraph-passive", "mindgraph-active-prefetch"],
        backend="reference",
        base_seed=42,
    )
    runner._verified_protocol = {"schedule_version": "balanced-v2"}
    scenarios = generate_development_v2(42, variants_per_family=5)
    schedule = runner._schedule(scenarios)

    positions = {condition: [] for condition in runner.conditions}
    for index in range(0, len(schedule), len(runner.conditions)):
        block = schedule[index : index + len(runner.conditions)]
        for position, (_, condition) in enumerate(block):
            positions[condition].append(position)
    assert all(set(values) == set(range(len(runner.conditions))) for values in positions.values())
