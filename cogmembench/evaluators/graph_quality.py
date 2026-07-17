from __future__ import annotations

from typing import Any


COGNITIVE_TYPES = {"preference", "claim", "evidence", "goal", "decision", "task", "execution", "policy"}


def graph_type_histogram(snapshot: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for record in snapshot.get("records", []):
        kind = str(record.get("primitive") or record.get("node_type") or "unknown").lower()
        out[kind] = out.get(kind, 0) + 1
    return out


def generic_dump_rate(snapshot: dict[str, Any]) -> float:
    kinds = graph_type_histogram(snapshot)
    total = sum(kinds.values())
    typed = sum(count for kind, count in kinds.items() if kind in COGNITIVE_TYPES)
    return 1 - typed / total if total else 0.0
