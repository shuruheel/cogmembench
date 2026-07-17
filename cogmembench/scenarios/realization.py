from __future__ import annotations

from dataclasses import dataclass, replace

from .schema import Event, Scenario


@dataclass(frozen=True)
class RealizationPack:
    pack_id: str
    author_origin: str
    independently_authored: bool
    description: str


PUBLICATION_HOLDOUT_V1 = RealizationPack(
    pack_id="publication-holdout-v1",
    author_origin="cogmembench implementation team",
    independently_authored=False,
    description="Distinct discourse opening and lifecycle structure for publication holdout.",
)


def apply_publication_holdout_v1(scenario: Scenario) -> Scenario:
    """Apply a disclosed, non-independent holdout realization without changing hidden answers."""
    family_openings = {
        "bitemporal_belief_revision": (
            "A background note unrelated to launch scheduling: the accessibility review remains "
            "in its ordinary queue. Treat subsequent reports according to when they became known."
        ),
        "recursive_investigation": (
            "Before the investigation begins, an unrelated documentation cleanup completed. "
            "It provides no evidence about the incident root cause."
        ),
        "decision_lineage": (
            "A routine, unrelated maintenance ticket closed before this incident. Exclude it from "
            "the later decision record unless a subsequent event explicitly makes it relevant."
        ),
    }
    opening = Event(
        session_id="holdout-preface",
        turn_id=0,
        role="system",
        content=family_openings[scenario.public.family],
        event_time=0,
        report_time=0,
        event_id=f"{scenario.public.scenario_id}:holdout-preface",
        phase="accumulate",
    )
    public = replace(scenario.public, events=(opening, *scenario.public.events))
    hidden = dict(scenario.hidden_world)
    hidden["realization_pattern"] = (
        f"{PUBLICATION_HOLDOUT_V1.pack_id}:"
        f"{hidden.get('realization_pattern', 'unspecified')}"
    )
    hidden["realization_pack"] = {
        "pack_id": PUBLICATION_HOLDOUT_V1.pack_id,
        "author_origin": PUBLICATION_HOLDOUT_V1.author_origin,
        "independently_authored": PUBLICATION_HOLDOUT_V1.independently_authored,
        "description": PUBLICATION_HOLDOUT_V1.description,
    }
    return replace(scenario, public=public, hidden_world=hidden)
