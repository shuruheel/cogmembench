from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..substrate import (
    ArtifactKind,
    CognitiveArtifact,
    EpistemicStatus,
    RelationKind,
    RetrievalBudget,
    RetrievalRepresentation,
    SubstrateAdapter,
    TimeInterval,
    Visibility,
    render_canonical_artifact,
)


def _function(name: str, description: str, properties: dict[str, Any], required: list[str]):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": properties,
                "required": required,
            },
        },
    }


COGNITIVE_TOOLS = [
    _function(
        "substrate_record",
        "Record an explicit, externally meaningful cognitive artifact.",
        {
            "artifact_id": {"type": "string"},
            "kind": {"type": "string", "enum": [kind.value for kind in ArtifactKind]},
            "content": {"type": "string"},
            "valid_start": {"type": "integer", "minimum": 0},
            "valid_end": {"type": ["integer", "null"], "minimum": 0},
            "status": {
                "type": "string",
                "enum": [status.value for status in EpistemicStatus],
            },
            "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
            "entity_scope": {"type": "array", "items": {"type": "string"}},
            "provenance_event_ids": {"type": "array", "items": {"type": "string"}},
        },
        ["artifact_id", "kind", "content", "valid_start"],
    ),
    _function(
        "substrate_revise",
        "Create a new artifact revision without erasing the historical version.",
        {
            "artifact_id": {"type": "string"},
            "revision_id": {"type": "string"},
            "kind": {"type": "string", "enum": [kind.value for kind in ArtifactKind]},
            "content": {"type": "string"},
            "valid_start": {"type": "integer", "minimum": 0},
            "valid_end": {"type": ["integer", "null"], "minimum": 0},
            "status": {
                "type": "string",
                "enum": [status.value for status in EpistemicStatus],
            },
            "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
            "provenance_event_ids": {"type": "array", "items": {"type": "string"}},
        },
        ["artifact_id", "revision_id", "kind", "content", "valid_start"],
    ),
    _function(
        "substrate_link",
        "Record a semantically testable relation between two artifacts.",
        {
            "source_id": {"type": "string"},
            "relation": {"type": "string", "enum": [kind.value for kind in RelationKind]},
            "target_id": {"type": "string"},
            "strength": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
        },
        ["source_id", "relation", "target_id"],
    ),
    _function(
        "substrate_retrieve",
        "Retrieve bounded cognitive context, optionally at valid and knowledge times.",
        {
            "query": {"type": "string"},
            "max_items": {"type": "integer", "minimum": 1, "maximum": 50},
            "max_context_tokens": {"type": ["integer", "null"], "minimum": 1},
            "valid_at": {"type": ["integer", "null"], "minimum": 0},
            "known_at": {"type": ["integer", "null"], "minimum": 0},
        },
        ["query", "max_items"],
    ),
    _function(
        "substrate_audit",
        "Export the recorded decision-time basis for an explicit decision artifact.",
        {"decision_ref": {"type": "string"}},
        ["decision_ref"],
    ),
]


@dataclass(frozen=True)
class CognitiveOperationContext:
    scenario_id: str
    logical_time: int
    actor_id: str
    session_id: str
    turn_id: int


class CognitiveOperationDispatcher:
    """Map benchmark-standard cognitive operations onto a substrate adapter."""

    def __init__(self, adapter: SubstrateAdapter) -> None:
        self.adapter = adapter

    @staticmethod
    def _interval(args: dict[str, Any]) -> TimeInterval:
        end = args.get("valid_end")
        return TimeInterval(int(args["valid_start"]), int(end) if end is not None else None)

    @staticmethod
    def _status(args: dict[str, Any]) -> EpistemicStatus:
        return EpistemicStatus(args.get("status", EpistemicStatus.PROPOSED.value))

    def _artifact(
        self,
        artifact_id: str,
        args: dict[str, Any],
        context: CognitiveOperationContext,
    ) -> CognitiveArtifact:
        confidence = args.get("confidence")
        return CognitiveArtifact(
            artifact_id=artifact_id,
            kind=ArtifactKind(args["kind"]),
            content=str(args["content"]),
            scenario_id=context.scenario_id,
            valid_time=self._interval(args),
            epistemic_status=self._status(args),
            confidence=float(confidence) if confidence is not None else None,
            actor_id=context.actor_id,
            session_id=context.session_id,
            turn_id=context.turn_id,
            entity_scope=tuple(str(value) for value in args.get("entity_scope", ())),
            provenance_event_ids=tuple(
                str(value) for value in args.get("provenance_event_ids", ())
            ),
            visibility=Visibility.AGENT,
        )

    def execute(
        self,
        name: str,
        args: dict[str, Any],
        context: CognitiveOperationContext,
    ) -> dict[str, Any]:
        if name == "substrate_record":
            artifact = self._artifact(str(args["artifact_id"]), args, context)
            stored = self.adapter.commit(artifact, context.logical_time)
            return {"artifact_id": stored.artifact_id, "kind": stored.kind.value}
        if name == "substrate_revise":
            revision = self._artifact(str(args["revision_id"]), args, context)
            stored = self.adapter.revise(str(args["artifact_id"]), revision, context.logical_time)
            return {
                "artifact_id": stored.artifact_id,
                "revision_of": stored.revision_of,
                "kind": stored.kind.value,
            }
        if name == "substrate_link":
            relation = self.adapter.link(
                str(args["source_id"]),
                RelationKind(args["relation"]),
                str(args["target_id"]),
                context.logical_time,
                strength=(float(args["strength"]) if args.get("strength") is not None else None),
            )
            return {"relation_id": relation.relation_id, "kind": relation.kind.value}
        if name == "substrate_retrieve":
            result = self.adapter.retrieve(
                str(args["query"]),
                RetrievalBudget(
                    max_items=int(args["max_items"]),
                    max_context_tokens=(
                        int(args["max_context_tokens"])
                        if args.get("max_context_tokens") is not None
                        else None
                    ),
                ),
                context.logical_time,
                valid_at=(int(args["valid_at"]) if args.get("valid_at") is not None else None),
                known_at=(int(args["known_at"]) if args.get("known_at") is not None else None),
            )
            canonical = (
                self.adapter.capability_manifest().retrieval_representation
                is RetrievalRepresentation.CANONICAL
            )
            return {
                "query": result.query,
                "logical_time": result.logical_time,
                "truncated": result.truncated,
                "results": [
                    {
                        "artifact_id": item.artifact.artifact_id,
                        "kind": item.artifact.kind.value,
                        "content": (
                            render_canonical_artifact(item.artifact)
                            if canonical
                            else item.artifact.content
                        ),
                        "status": item.artifact.epistemic_status.value,
                        "score": item.score,
                        "retrieval_metadata": item.metadata,
                    }
                    for item in result.items
                ],
            }
        if name == "substrate_audit":
            receipt = self.adapter.export_audit(str(args["decision_ref"]))
            return asdict(receipt)
        raise ValueError(f"unsupported cognitive operation: {name}")
