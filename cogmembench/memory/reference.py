from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .flat_store import FlatMemoryStore


@dataclass
class CognitiveRecord:
    uid: str
    primitive: str
    label: str
    text: str
    session_id: str
    agent_id: str
    confidence: float = 0.7
    salience: float = 0.5
    version: int = 1
    superseded_by: str | None = None
    provenance: list[str] = field(default_factory=list)


class ReferenceCognitiveMemory:
    """Deterministic test double. It is intentionally labeled non-MindGraph."""

    backend_label = "reference"

    def __init__(self, agent_id: str = "cogmembench"):
        self.agent_id = agent_id
        self.records: list[CognitiveRecord] = []
        self.edges: list[dict[str, str]] = []
        self._search = FlatMemoryStore()

    def reset(self) -> None:
        self.records.clear()
        self.edges.clear()
        self._search.reset()

    def _uid(self, primitive: str, text: str) -> str:
        base = hashlib.sha1(f"{primitive}\0{text}\0{len(self.records)}".encode()).hexdigest()[:16]
        return f"ref-{base}"

    def write(self, primitive: str, text: str, session_id: str, *, label: str = "", confidence: float = 0.7) -> CognitiveRecord:
        normalized = " ".join(text.lower().split())
        for record in self.records:
            if record.primitive == primitive and " ".join(record.text.lower().split()) == normalized:
                return record
        record = CognitiveRecord(self._uid(primitive, text), primitive, label or text[:100], text, session_id, self.agent_id, confidence)
        if "supersedes" in text.lower() or "correction:" in text.lower() or "retracted" in text.lower():
            candidates = [r for r in self.records if r.primitive in {primitive, "claim", "preference"} and not r.superseded_by]
            if candidates:
                candidates[-1].superseded_by = record.uid
                self.edges.append({"from_uid": record.uid, "to_uid": candidates[-1].uid, "edge_type": "Supersedes"})
        self.records.append(record)
        self._search.add(text, session_id, {"uid": record.uid, "primitive": primitive})
        return record

    def ingest_session(self, session_id: str, messages: list[str]) -> list[CognitiveRecord]:
        written = []
        for text in messages:
            low = text.lower()
            if "temporary detail:" in low or "not project state" in low:
                continue
            primitive = "observation"
            if any(k in low for k in ("prefer", "always avoid", "correction:")):
                primitive = "preference"
            elif any(k in low for k in ("source alpha", "authoritative", "retracted", "provisional claim")):
                primitive = "claim"
            elif low.startswith("project ") or "objective is" in low:
                primitive = "goal"
            elif "decision:" in low:
                primitive = "decision"
            elif "completed" in low or "depends on" in low:
                primitive = "task"
            elif "failed" in low:
                primitive = "execution"
            elif "lesson applies" in low:
                primitive = "policy"
            written.append(self.write(primitive, text, session_id, label=text[:100]))
        return written

    def retrieve(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        hits = self._search.search(query, k)
        by_uid = {record.uid: record for record in self.records}
        out = []
        for hit in hits:
            uid = hit["metadata"].get("uid")
            if uid in by_uid:
                row = asdict(by_uid[uid])
                row["score"] = hit["score"]
                out.append(row)
        return out

    def execute_tool(self, name: str, args: dict[str, Any], session_id: str) -> dict[str, Any]:
        if name == "mindgraph_retrieve":
            return {"results": self.retrieve(str(args.get("query", "")), int(args.get("limit", 5)))}
        action = str(args.get("action", "observation"))
        text = str(args.get("summary") or args.get("label") or args)
        mapping = {
            "mindgraph_capture": "preference" if action == "preference" else "observation",
            "mindgraph_reason": "claim" if action == "claim" else action,
            "mindgraph_commit": "decision" if "decision" in action else ("goal" if action in {"goal", "project"} else action),
            "mindgraph_plan": "execution" if "execution" in action else ("policy" if "policy" in action else "task"),
        }
        record = self.write(mapping.get(name, action), text, session_id, label=str(args.get("label", "")))
        return {"uid": record.uid, "primitive": record.primitive}

    def snapshot(self) -> dict[str, Any]:
        return {
            "backend": self.backend_label,
            "records": [asdict(record) for record in self.records],
            "edges": list(self.edges),
            "node_count": len(self.records),
            "edge_count": len(self.edges),
        }


def primitive_from_text(text: str) -> str:
    low = text.lower()
    for pattern, primitive in ((r"prefer|avoid", "preference"), (r"claim|source|evidence", "claim"), (r"decision", "decision"), (r"project|objective", "goal"), (r"failed", "execution")):
        if re.search(pattern, low):
            return primitive
    return "observation"

