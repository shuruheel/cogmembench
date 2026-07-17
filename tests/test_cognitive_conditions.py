from __future__ import annotations

import pytest

from cogmembench.substrate import (
    COGNITIVE_V2_CONDITIONS,
    CaptureMode,
    CognitiveCondition,
    RetrievalPolicy,
)


def test_cognitive_condition_matrix_separates_capture_from_retrieval():
    automatic = COGNITIVE_V2_CONDITIONS["automatic-passive"]
    directed = COGNITIVE_V2_CONDITIONS["agent-directed-active"]
    oracle = COGNITIVE_V2_CONDITIONS["oracle-passive"]
    matched = COGNITIVE_V2_CONDITIONS["transcript"]
    full = COGNITIVE_V2_CONDITIONS["transcript-full"]

    assert automatic.capture_mode is CaptureMode.AUTOMATIC
    assert automatic.retrieval_policy is RetrievalPolicy.PASSIVE_PREFETCH
    assert directed.capture_mode is CaptureMode.AGENT_DIRECTED
    assert directed.retrieval_policy is RetrievalPolicy.ACTIVE_PULL
    assert oracle.capture_mode is CaptureMode.ORACLE
    assert oracle.instrumented_track
    assert matched.transcript_replay and not matched.full_transcript
    assert full.transcript_replay and full.full_transcript


def test_invalid_condition_crossings_are_rejected():
    with pytest.raises(ValueError, match="persistent conditions require"):
        CognitiveCondition(
            "invalid",
            CaptureMode.NONE,
            RetrievalPolicy.NONE,
            persistent=True,
        )
    with pytest.raises(ValueError, match="retrieval policies require"):
        CognitiveCondition(
            "invalid",
            CaptureMode.NONE,
            RetrievalPolicy.ACTIVE_PULL,
            persistent=False,
        )
    with pytest.raises(ValueError, match="full transcript requires"):
        CognitiveCondition(
            "invalid",
            CaptureMode.NONE,
            RetrievalPolicy.NONE,
            persistent=False,
            full_transcript=True,
        )
