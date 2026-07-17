from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..validation.generator_validity import (
    causal_content_fingerprint,
    structural_fingerprint,
    world_fingerprint,
)
from .schema import Scenario, save_jsonl

WORD = re.compile(r"[a-z0-9]+")
SPLITS = {"unit", "development", "calibration", "publication", "challenge"}


def _ngrams(scenario: Scenario, n: int) -> set[tuple[str, ...]]:
    words = WORD.findall(" ".join(event.content.lower() for event in scenario.public.events))
    return {tuple(words[index : index + n]) for index in range(len(words) - n + 1)}


def audit_split_separation(
    candidate: list[Scenario],
    references: dict[str, list[Scenario]],
    *,
    ngram_size: int = 8,
) -> dict[str, Any]:
    if ngram_size < 3:
        raise ValueError("ngram_size must be at least 3")
    candidate_hashes = {row.public_hash() for row in candidate}
    candidate_structures = {structural_fingerprint(row) for row in candidate}
    candidate_worlds = {world_fingerprint(row) for row in candidate}
    candidate_causal_content = {causal_content_fingerprint(row) for row in candidate}
    candidate_patterns = {
        (row.public.family, str(row.hidden_world.get("realization_pattern", "unspecified")))
        for row in candidate
    }
    candidate_ngrams = set().union(*(_ngrams(row, ngram_size) for row in candidate)) if candidate else set()
    comparisons = {}
    passed = True
    for name, rows in sorted(references.items()):
        reference_ngrams = set().union(*(_ngrams(row, ngram_size) for row in rows)) if rows else set()
        overlap = candidate_ngrams & reference_ngrams
        result = {
            "public_hash_overlap": len(candidate_hashes & {row.public_hash() for row in rows}),
            "causal_world_overlap": len(candidate_worlds & {world_fingerprint(row) for row in rows}),
            "causal_content_overlap": len(
                candidate_causal_content
                & {causal_content_fingerprint(row) for row in rows}
            ),
            "structural_fingerprint_overlap": len(
                candidate_structures & {structural_fingerprint(row) for row in rows}
            ),
            "realization_pattern_overlap": len(
                candidate_patterns
                & {
                    (
                        row.public.family,
                        str(row.hidden_world.get("realization_pattern", "unspecified")),
                    )
                    for row in rows
                }
            ),
            "shared_ngrams": len(overlap),
            "candidate_ngram_overlap_rate": (
                len(overlap) / len(candidate_ngrams) if candidate_ngrams else 0.0
            ),
            "sample_shared_ngrams": [" ".join(value) for value in sorted(overlap)[:20]],
        }
        result["strict_structural_holdout"] = all(
            result[key] == 0
            for key in (
                "public_hash_overlap",
                "causal_world_overlap",
                "causal_content_overlap",
                "structural_fingerprint_overlap",
                "realization_pattern_overlap",
            )
        )
        passed = passed and result["strict_structural_holdout"]
        comparisons[name] = result
    return {
        "schema_version": 1,
        "candidate_scenarios": len(candidate),
        "ngram_size": ngram_size,
        "comparisons": comparisons,
        "passed": passed,
    }


def prepare_release(
    scenarios: list[Scenario],
    output: Path,
    *,
    split: str,
    references: dict[str, list[Scenario]] | None = None,
    canary_guid: str | None = None,
    ngram_size: int = 8,
) -> dict[str, Any]:
    if split not in SPLITS:
        raise ValueError(f"unknown split: {split}")
    if not scenarios:
        raise ValueError("release requires scenarios")
    canary = canary_guid or str(uuid.uuid4())
    uuid.UUID(canary)
    audit = audit_split_separation(scenarios, references or {}, ngram_size=ngram_size)
    if split in {"publication", "challenge"} and references and not audit["passed"]:
        raise ValueError("publication/challenge split is not a strict structural holdout")
    prepared_at = datetime.now(timezone.utc).isoformat()
    released = []
    for scenario in scenarios:
        hidden = dict(scenario.hidden_world)
        hidden["release"] = {
            "schema_version": 1,
            "split": split,
            "canary_guid": canary,
            "prepared_at": prepared_at,
            "structural_fingerprint": structural_fingerprint(scenario),
            "world_fingerprint": world_fingerprint(scenario),
            "causal_content_fingerprint": causal_content_fingerprint(scenario),
            "realization_pattern": hidden.get("realization_pattern", "unspecified"),
        }
        released.append(replace(scenario, hidden_world=hidden))
    save_jsonl(output, released)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "split": split,
        "canary_guid": canary,
        "prepared_at": prepared_at,
        "scenario_count": len(released),
        "dataset": str(output),
        "dataset_sha256": digest,
        "contamination_audit": audit,
    }
    manifest_path = output.with_suffix(output.suffix + ".release.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {**manifest, "manifest": str(manifest_path)}
