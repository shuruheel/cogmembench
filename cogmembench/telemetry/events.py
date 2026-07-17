from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TraceEvent:
    event_type: str
    scenario_id: str
    condition: str
    session_id: str = ""
    turn_id: int = 0
    timestamp: float = field(default_factory=time.time)
    duration_ms: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class EventLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event), sort_keys=True, default=str) + "\n")

    def by_type(self, event_type: str) -> list[TraceEvent]:
        return [event for event in self.events if event.event_type == event_type]

