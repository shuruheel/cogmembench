from __future__ import annotations

from cogmembench.scenarios.generators import generate_bitemporal_belief_revision
from cogmembench.scenarios.realization import apply_publication_holdout_v1
from cogmembench.scenarios.release import audit_split_separation
from cogmembench.validation import causal_content_fingerprint, structural_fingerprint


def test_publication_realization_changes_structure_but_not_causal_content() -> None:
    development = generate_bitemporal_belief_revision(9, 8, 3)
    publication = [apply_publication_holdout_v1(row) for row in development]
    assert structural_fingerprint(development[0]) != structural_fingerprint(publication[0])
    assert causal_content_fingerprint(development[0]) == causal_content_fingerprint(publication[0])
    assert publication[0].hidden_world["realization_pack"]["independently_authored"] is False

    audit = audit_split_separation(publication, {"development": development})
    assert audit["comparisons"]["development"]["structural_fingerprint_overlap"] == 0
    assert audit["comparisons"]["development"]["causal_content_overlap"] > 0
    assert not audit["passed"]
