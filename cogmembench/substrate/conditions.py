from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CaptureMode(str, Enum):
    NONE = "none"
    AUTOMATIC = "automatic"
    AGENT_DIRECTED = "agent_directed"
    ORACLE = "oracle"


class RetrievalPolicy(str, Enum):
    NONE = "none"
    PASSIVE_PREFETCH = "passive_prefetch"
    ACTIVE_PULL = "active_pull"


@dataclass(frozen=True)
class CognitiveCondition:
    condition_id: str
    capture_mode: CaptureMode
    retrieval_policy: RetrievalPolicy
    persistent: bool
    transcript_replay: bool = False
    full_transcript: bool = False
    instrumented_track: bool = False

    def __post_init__(self) -> None:
        if not self.condition_id:
            raise ValueError("condition_id is required")
        if self.capture_mode is CaptureMode.NONE and self.persistent:
            raise ValueError("persistent conditions require a capture mode")
        if self.capture_mode is not CaptureMode.NONE and not self.persistent:
            raise ValueError("capture modes require persistent storage")
        if self.retrieval_policy is not RetrievalPolicy.NONE and not self.persistent:
            raise ValueError("retrieval policies require persistent storage")
        if self.transcript_replay and self.persistent:
            raise ValueError("transcript replay is a non-persistent baseline")
        if self.full_transcript and not self.transcript_replay:
            raise ValueError("full transcript requires transcript replay")
        if self.instrumented_track and not self.persistent:
            raise ValueError("instrumented-track conditions require a substrate")


COGNITIVE_V2_CONDITIONS = {
    condition.condition_id: condition
    for condition in (
        CognitiveCondition(
            "stateless",
            CaptureMode.NONE,
            RetrievalPolicy.NONE,
            persistent=False,
        ),
        CognitiveCondition(
            "transcript",
            CaptureMode.NONE,
            RetrievalPolicy.NONE,
            persistent=False,
            transcript_replay=True,
        ),
        CognitiveCondition(
            "transcript-full",
            CaptureMode.NONE,
            RetrievalPolicy.NONE,
            persistent=False,
            transcript_replay=True,
            full_transcript=True,
        ),
        CognitiveCondition(
            "automatic-passive",
            CaptureMode.AUTOMATIC,
            RetrievalPolicy.PASSIVE_PREFETCH,
            persistent=True,
        ),
        CognitiveCondition(
            "agent-directed-active",
            CaptureMode.AGENT_DIRECTED,
            RetrievalPolicy.ACTIVE_PULL,
            persistent=True,
            instrumented_track=True,
        ),
        CognitiveCondition(
            "oracle-passive",
            CaptureMode.ORACLE,
            RetrievalPolicy.PASSIVE_PREFETCH,
            persistent=True,
            instrumented_track=True,
        ),
    )
}
