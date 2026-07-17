from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scenarios.schema import load_jsonl


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_commit(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def freeze_protocol(
    output: Path,
    *,
    root: Path,
    protocol_id: str,
    scenario_file: Path,
    frozen_files: list[Path],
    models: list[str],
    conditions: list[str],
    primary_endpoints: dict[str, list[str]],
    exclusion_rules: list[str],
    analysis_plan: dict[str, Any],
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"protocol freeze is immutable: {output}")
    scenarios = load_jsonl(scenario_file)
    releases = [row.hidden_world.get("release", {}) for row in scenarios]
    canaries = {row.get("canary_guid") for row in releases if row.get("canary_guid")}
    splits = {row.get("split") for row in releases if row.get("split")}
    if len(canaries) != 1 or splits != {"publication"}:
        raise ValueError("freeze requires one canaried publication release")
    release_manifest = scenario_file.with_suffix(scenario_file.suffix + ".release.json")
    if not release_manifest.exists():
        raise FileNotFoundError(
            f"freeze requires adjacent release manifest: {release_manifest}"
        )
    release = json.loads(release_manifest.read_text())
    release_audit = release.get("contamination_audit", {})
    release_canary = release.get("canary_guid")
    if (
        release.get("split") != "publication"
        or release.get("scenario_count") != len(scenarios)
        or release.get("dataset_sha256") != _sha256(scenario_file)
        or release_canary != next(iter(canaries))
        or release_audit.get("passed") is not True
    ):
        raise ValueError("publication release manifest failed integrity verification")
    files = [scenario_file, release_manifest, *frozen_files]
    missing = [str(path) for path in files if not path.exists()]
    if missing:
        raise FileNotFoundError("missing frozen files: " + ", ".join(missing))
    file_hashes = {
        str(path.resolve().relative_to(root.resolve())): _sha256(path)
        for path in sorted(set(files))
    }
    manifest = {
        "schema_version": 1,
        "protocol_id": protocol_id,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "repository_commit": _repository_commit(root),
        "publication_scenarios": str(scenario_file.resolve().relative_to(root.resolve())),
        "publication_canary_guid": next(iter(canaries)),
        "publication_release_manifest": str(
            release_manifest.resolve().relative_to(root.resolve())
        ),
        "publication_separation_audit": release_audit,
        "scenario_count": len(scenarios),
        "models": models,
        "conditions": conditions,
        "primary_endpoints": primary_endpoints,
        "exclusion_rules": exclusion_rules,
        "analysis_plan": analysis_plan,
        "files": file_hashes,
        "fresh_world_attestation": (
            "The publication file and its passing separation audit were integrity-checked and "
            "included in this immutable freeze."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {**manifest, "freeze_sha256": _sha256(output)}


def verify_protocol_freeze(path: Path, *, root: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text())
    mismatches = []
    for relative, expected in manifest["files"].items():
        target = root / relative
        actual = _sha256(target) if target.exists() else None
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})
    return {
        "protocol_id": manifest["protocol_id"],
        "freeze_sha256": _sha256(path),
        "verified_files": len(manifest["files"]),
        "mismatches": mismatches,
        "passed": not mismatches,
    }
