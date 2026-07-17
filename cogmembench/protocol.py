from __future__ import annotations

import hashlib
import json
from typing import Any

from .config import ROOT


def verify_protocol_lock(protocol_id: str) -> dict[str, Any]:
    lock_path = ROOT / "configs" / "protocols" / f"{protocol_id}.json"
    if not lock_path.exists():
        raise ValueError(f"unknown protocol lock: {protocol_id}")
    lock = json.loads(lock_path.read_text())
    mismatches = []
    for relative, expected in lock.get("files", {}).items():
        path = ROOT / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})
    verified_external = []
    unavailable_external = []
    for relative, expected in lock.get("external_files", {}).items():
        path = ROOT / relative
        if not path.exists():
            unavailable_external.append(relative)
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})
        else:
            verified_external.append(relative)
    if mismatches:
        raise RuntimeError(
            f"protocol lock {protocol_id} drifted: " + json.dumps(mismatches, sort_keys=True)
        )
    local_files = len(lock.get("files", {}))
    external_files = len(lock.get("external_files", {}))
    result = {
        "protocol_id": protocol_id,
        "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        "frozen_at_commit": lock.get("frozen_at_commit"),
        "locked_files": local_files + external_files,
        "verified_files": local_files + len(verified_external),
        "verified_local_files": local_files,
        "verified_external_files": len(verified_external),
        "unavailable_external_files": unavailable_external,
        "complete": not unavailable_external,
    }
    for key in ("executor_version", "evaluator_version", "schedule_version"):
        if lock.get(key):
            result[key] = lock[key]
    return result
