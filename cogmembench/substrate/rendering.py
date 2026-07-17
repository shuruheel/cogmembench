from __future__ import annotations

import json

from .schema import CognitiveArtifact


def render_canonical_artifact(artifact: CognitiveArtifact) -> str:
    """Fixed oracle-capture text shared by flat and retrieval-oriented substrates."""
    valid_end = "open" if artifact.valid_time.end is None else str(artifact.valid_time.end)
    transaction = artifact.transaction_time
    transaction_text = (
        "unstamped"
        if transaction is None
        else f"{transaction.start}:{'open' if transaction.end is None else transaction.end}"
    )
    structured = json.dumps(
        artifact.structured_content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "\n".join(
        (
            f"artifact_id: {artifact.artifact_id}",
            f"kind: {artifact.kind.value}",
            f"status: {artifact.epistemic_status.value}",
            f"valid_time: {artifact.valid_time.start}:{valid_end}",
            f"transaction_time: {transaction_text}",
            f"entities: {', '.join(artifact.entity_scope)}",
            f"content: {artifact.content}",
            f"structured: {structured}",
        )
    )
