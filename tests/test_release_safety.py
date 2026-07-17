from __future__ import annotations

import json

import pytest

from cogmembench.scenarios.generators import generate_bitemporal_belief_revision
from cogmembench.scenarios.release import audit_split_separation, prepare_release
from cogmembench.scenarios.schema import load_jsonl


def test_release_embeds_canary_and_writes_hash_manifest(tmp_path) -> None:
    scenarios = generate_bitemporal_belief_revision(5, 8, 3)
    output = tmp_path / "calibration.jsonl"
    result = prepare_release(scenarios, output, split="calibration")
    loaded = load_jsonl(output)
    assert all(row.hidden_world["release"]["canary_guid"] == result["canary_guid"] for row in loaded)
    assert json.loads((tmp_path / "calibration.jsonl.release.json").read_text())["dataset_sha256"]


def test_publication_release_rejects_structural_overlap(tmp_path) -> None:
    scenarios = generate_bitemporal_belief_revision(5, 8, 3)
    audit = audit_split_separation(scenarios, {"development": scenarios})
    assert audit["passed"] is False
    with pytest.raises(ValueError, match="strict structural holdout"):
        prepare_release(
            scenarios,
            tmp_path / "publication.jsonl",
            split="publication",
            references={"development": scenarios},
        )
