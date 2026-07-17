from __future__ import annotations

import json

import pytest

from cogmembench.protocol_v2 import freeze_protocol, verify_protocol_freeze
from cogmembench.scenarios.generators import generate_bitemporal_belief_revision
from cogmembench.scenarios.release import prepare_release


def test_protocol_freeze_is_immutable_and_detects_drift(tmp_path) -> None:
    scenario_file = tmp_path / "publication.jsonl"
    prepare_release(
        generate_bitemporal_belief_revision(8, 8, 3),
        scenario_file,
        split="publication",
    )
    config = tmp_path / "config.json"
    config.write_text("{}")
    freeze = tmp_path / "freeze.json"
    freeze_protocol(
        freeze,
        root=tmp_path,
        protocol_id="publication-v2",
        scenario_file=scenario_file,
        frozen_files=[config],
        models=["snapshot-a"],
        conditions=["stateless", "automatic-passive"],
        primary_endpoints={"RQ2": ["trace_verified_reuse_accuracy"]},
        exclusion_rules=["exclude only predeclared infrastructure failures"],
        analysis_plan={"unit": "scenario/world"},
    )
    assert verify_protocol_freeze(freeze, root=tmp_path)["passed"]
    frozen = json.loads(freeze.read_text())
    assert frozen["publication_separation_audit"]["passed"]
    assert "publication.jsonl.release.json" in frozen["files"]
    with pytest.raises(FileExistsError):
        freeze_protocol(
            freeze,
            root=tmp_path,
            protocol_id="publication-v2",
            scenario_file=scenario_file,
            frozen_files=[config],
            models=[],
            conditions=[],
            primary_endpoints={},
            exclusion_rules=[],
            analysis_plan={},
        )
    config.write_text('{"drift": true}')
    assert not verify_protocol_freeze(freeze, root=tmp_path)["passed"]


def test_protocol_freeze_rejects_tampered_release_manifest(tmp_path) -> None:
    scenario_file = tmp_path / "publication.jsonl"
    prepare_release(
        generate_bitemporal_belief_revision(8, 8, 3),
        scenario_file,
        split="publication",
    )
    release_path = scenario_file.with_suffix(".jsonl.release.json")
    release = json.loads(release_path.read_text())
    release["dataset_sha256"] = "0" * 64
    release_path.write_text(json.dumps(release))

    with pytest.raises(ValueError, match="integrity verification"):
        freeze_protocol(
            tmp_path / "freeze.json",
            root=tmp_path,
            protocol_id="publication-v2",
            scenario_file=scenario_file,
            frozen_files=[],
            models=["snapshot-a"],
            conditions=["stateless"],
            primary_endpoints={"RQ1": ["task_success"]},
            exclusion_rules=[],
            analysis_plan={"unit": "scenario/world"},
        )
