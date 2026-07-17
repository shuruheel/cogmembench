from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any

from ..scenarios.schema import Event
from .adapter import (
    CapabilityManifest,
    ClockMode,
    RetrievalBudget,
    RetrievalResult,
    SnapshotResult,
    SubstrateAdapter,
    UnsupportedCapabilityError,
    UsageReport,
)
from .schema import (
    ArtifactKind,
    AuditReceipt,
    CognitiveArtifact,
    CognitiveRelation,
    EpistemicStatus,
    RelationKind,
    TimeInterval,
    Visibility,
)


class AblationFeature(str, Enum):
    NO_PROVENANCE_LINKS = "no-provenance-links"
    NO_TEMPORAL_METADATA = "no-temporal-metadata"
    NO_EVIDENCE_CLAIM_DISTINCTION = "no-evidence-claim-distinction"
    NO_STORED_INTERMEDIATE_CONCLUSIONS = "no-stored-intermediate-conclusions"
    NO_DEPENDENCY_TRACKING = "no-dependency-tracking"
    NO_SUPERSESSION = "no-supersession"
    NO_ACTIVE_RETRIEVAL = "no-active-retrieval"
    NO_LESSON_CONSOLIDATION = "no-lesson-consolidation"
    NO_AUDIT_RECEIPT = "no-audit-receipt"


@dataclass(frozen=True)
class AblationSpec:
    feature: AblationFeature
    layer: str
    opportunity_families: tuple[str, ...]
    removed_operations: tuple[str, ...]
    opportunity_conditions: tuple[str, ...] = (
        "automatic-passive",
        "agent-directed-active",
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["feature"] = self.feature.value
        return data


CORE_FAMILIES = (
    "bitemporal_belief_revision",
    "recursive_investigation",
    "decision_lineage",
)


ABLATION_SPECS = {
    spec.feature: spec
    for spec in (
        AblationSpec(
            AblationFeature.NO_PROVENANCE_LINKS,
            "substrate",
            CORE_FAMILIES,
            ("artifact_provenance", "derived_from", "learned_from"),
        ),
        AblationSpec(
            AblationFeature.NO_TEMPORAL_METADATA,
            "substrate",
            ("bitemporal_belief_revision", "decision_lineage"),
            ("valid_time", "known_at", "historical_snapshot"),
        ),
        AblationSpec(
            AblationFeature.NO_EVIDENCE_CLAIM_DISTINCTION,
            "substrate",
            ("bitemporal_belief_revision", "decision_lineage"),
            ("evidence_kind", "claim_kind"),
        ),
        AblationSpec(
            AblationFeature.NO_STORED_INTERMEDIATE_CONCLUSIONS,
            "substrate",
            ("recursive_investigation",),
            ("hypothesis_storage", "conclusion_storage"),
        ),
        AblationSpec(
            AblationFeature.NO_DEPENDENCY_TRACKING,
            "substrate",
            ("bitemporal_belief_revision", "recursive_investigation"),
            ("depends_on", "invalidates"),
        ),
        AblationSpec(
            AblationFeature.NO_SUPERSESSION,
            "substrate",
            ("bitemporal_belief_revision",),
            ("revision_closure", "supersedes"),
        ),
        AblationSpec(
            AblationFeature.NO_ACTIVE_RETRIEVAL,
            "agent-policy",
            CORE_FAMILIES,
            ("substrate_retrieve_tool",),
            ("agent-directed-active",),
        ),
        AblationSpec(
            AblationFeature.NO_LESSON_CONSOLIDATION,
            "substrate",
            (),
            ("lesson_storage", "rule_storage", "policy_storage"),
        ),
        AblationSpec(
            AblationFeature.NO_AUDIT_RECEIPT,
            "substrate-and-agent-policy",
            ("decision_lineage",),
            ("audit_export", "substrate_audit_tool"),
            ("agent-directed-active",),
        ),
    )
}


class AblatedSubstrateAdapter:
    """Representation-neutral single-feature removal around a substrate adapter."""

    def __init__(self, delegate: SubstrateAdapter, feature: AblationFeature | str):
        self.delegate = delegate
        self.feature = AblationFeature(feature)
        self._suppressed_artifact_ids: set[str] = set()
        self._namespace: str | None = None

    @property
    def spec(self) -> AblationSpec:
        return ABLATION_SPECS[self.feature]

    def reset(self, namespace: str) -> None:
        self._suppressed_artifact_ids.clear()
        self._namespace = namespace
        self.delegate.reset(namespace)

    def quiesce(self) -> None:
        self.delegate.quiesce()

    def close_session(self, session_id: str, logical_time: int) -> None:
        self.delegate.close_session(session_id, logical_time)

    def _transform_artifact(
        self, artifact: CognitiveArtifact, logical_time: int
    ) -> CognitiveArtifact:
        transformed = artifact
        if self.feature is AblationFeature.NO_PROVENANCE_LINKS:
            transformed = replace(transformed, provenance_event_ids=())
        if self.feature is AblationFeature.NO_TEMPORAL_METADATA:
            transformed = replace(transformed, valid_time=TimeInterval(logical_time))
        if (
            self.feature is AblationFeature.NO_EVIDENCE_CLAIM_DISTINCTION
            and transformed.kind in {ArtifactKind.EVIDENCE, ArtifactKind.CLAIM}
        ):
            transformed = replace(transformed, kind=ArtifactKind.OBSERVATION)
        return transformed

    def _suppresses_artifact(self, artifact: CognitiveArtifact) -> bool:
        if self.feature is AblationFeature.NO_STORED_INTERMEDIATE_CONCLUSIONS:
            return artifact.kind in {ArtifactKind.HYPOTHESIS, ArtifactKind.CONCLUSION}
        if self.feature is AblationFeature.NO_LESSON_CONSOLIDATION:
            return artifact.kind in {ArtifactKind.LESSON, ArtifactKind.RULE, ArtifactKind.POLICY}
        return False

    def observe(self, event: Event, logical_time: int) -> CognitiveArtifact:
        event_id = event.event_id or f"event:{event.session_id}:{event.turn_id}"
        artifact = CognitiveArtifact(
            artifact_id=event_id,
            kind=ArtifactKind.OBSERVATION,
            content=event.content,
            scenario_id=self._namespace or "",
            valid_time=TimeInterval(
                event.event_time if event.event_time is not None else logical_time
            ),
            epistemic_status=EpistemicStatus.ACCEPTED,
            actor_id=event.role,
            session_id=event.session_id,
            turn_id=event.turn_id,
            provenance_event_ids=(event_id,),
            visibility=Visibility.PUBLIC,
        )
        return self.commit(artifact, logical_time)

    def commit(self, artifact: CognitiveArtifact, logical_time: int) -> CognitiveArtifact:
        transformed = self._transform_artifact(artifact, logical_time)
        if self._suppresses_artifact(transformed):
            self._suppressed_artifact_ids.add(transformed.artifact_id)
            return replace(transformed, transaction_time=TimeInterval(logical_time))
        return self.delegate.commit(transformed, logical_time)

    def revise(
        self,
        artifact_id: str,
        revision: CognitiveArtifact,
        logical_time: int,
    ) -> CognitiveArtifact:
        transformed = self._transform_artifact(revision, logical_time)
        if self._suppresses_artifact(transformed):
            self._suppressed_artifact_ids.add(transformed.artifact_id)
            return replace(transformed, transaction_time=TimeInterval(logical_time))
        if self.feature is AblationFeature.NO_SUPERSESSION:
            return self.delegate.commit(replace(transformed, revision_of=None), logical_time)
        return self.delegate.revise(artifact_id, transformed, logical_time)

    def _suppresses_relation(
        self, source_id: str, relation: RelationKind, target_id: str
    ) -> bool:
        if source_id in self._suppressed_artifact_ids or target_id in self._suppressed_artifact_ids:
            return True
        if self.feature is AblationFeature.NO_PROVENANCE_LINKS:
            return relation in {RelationKind.DERIVED_FROM, RelationKind.LEARNED_FROM}
        if self.feature is AblationFeature.NO_DEPENDENCY_TRACKING:
            return relation in {RelationKind.DEPENDS_ON, RelationKind.INVALIDATES}
        if self.feature is AblationFeature.NO_SUPERSESSION:
            return relation is RelationKind.SUPERSEDES
        return False

    def link(
        self,
        source_id: str,
        relation: RelationKind,
        target_id: str,
        logical_time: int,
        *,
        strength: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CognitiveRelation:
        if self._suppresses_relation(source_id, relation, target_id):
            digest = hashlib.sha256(
                f"ablated\0{source_id}\0{relation.value}\0{target_id}\0{logical_time}".encode()
            ).hexdigest()[:16]
            return CognitiveRelation(
                relation_id=f"ablated-relation:{digest}",
                source_id=source_id,
                kind=relation,
                target_id=target_id,
                created_at=logical_time,
                strength=strength,
                source="cogmembench-ablation",
                metadata={"persisted": False, "ablation": self.feature.value},
            )
        return self.delegate.link(
            source_id,
            relation,
            target_id,
            logical_time,
            strength=strength,
            metadata=metadata,
        )

    def retrieve(
        self,
        query: str,
        budget: RetrievalBudget,
        logical_time: int,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> RetrievalResult:
        if self.feature is AblationFeature.NO_TEMPORAL_METADATA:
            valid_at = None
            known_at = None
        return self.delegate.retrieve(query, budget, logical_time, valid_at, known_at)

    def snapshot(
        self,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> SnapshotResult:
        if self.feature is AblationFeature.NO_TEMPORAL_METADATA:
            valid_at = None
            known_at = None
        return self.delegate.snapshot(valid_at, known_at)

    def export_audit(self, decision_ref: str) -> AuditReceipt:
        if self.feature is AblationFeature.NO_AUDIT_RECEIPT:
            raise UnsupportedCapabilityError("audit receipt removed by ablation")
        return self.delegate.export_audit(decision_ref)

    def usage_report(self) -> UsageReport:
        return self.delegate.usage_report()

    def capability_manifest(self) -> CapabilityManifest:
        manifest = self.delegate.capability_manifest()
        changes: dict[str, Any] = {
            "adapter_name": f"{manifest.adapter_name}+{self.feature.value}",
            "notes": (*manifest.notes, f"ablation={self.feature.value}"),
        }
        if self.feature is AblationFeature.NO_TEMPORAL_METADATA:
            changes.update(clock_mode=ClockMode.NONE, snapshot=False)
        if self.feature is AblationFeature.NO_SUPERSESSION:
            changes["revision"] = False
        if self.feature is AblationFeature.NO_AUDIT_RECEIPT:
            changes["audit_export"] = False
        return replace(manifest, **changes)


def ablation_manifest(feature: AblationFeature | str) -> dict[str, Any]:
    return ABLATION_SPECS[AblationFeature(feature)].to_dict()
