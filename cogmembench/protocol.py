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
    if mismatches:
        raise RuntimeError(
            f"protocol lock {protocol_id} drifted: " + json.dumps(mismatches, sort_keys=True)
        )
    result = {
        "protocol_id": protocol_id,
        "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        "frozen_at_commit": lock.get("frozen_at_commit"),
        "verified_files": len(lock.get("files", {})),
    }
    for key in ("executor_version", "evaluator_version", "schedule_version"):
        if lock.get(key):
            result[key] = lock[key]
    return result
