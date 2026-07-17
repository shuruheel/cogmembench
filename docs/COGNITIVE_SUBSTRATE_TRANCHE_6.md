# Cognitive Substrate Tranche 6

Status: procedural target-scale worlds and mechanical branch oracles implemented on 2026-07-17.

## Scope delivered

- Removed the five-variant ceiling from all three cognitive-v2 generators.
- Seeded, parameterized bitemporal facts now vary entity, source revisions, provisional and
  corrected values, and dependent decisions.
- Seeded service incidents now vary causal mechanism parameters, root placement, service IDs,
  and dependency topology rather than merely shuffling distractors.
- Added explicit easy, medium, and hard strata. The tiers control bitemporal distractor load,
  recursive premise count and DAG depth, decision-context burden, and service topology depth.
- Added three cognitive-v2 generation profiles without changing the locked schema-v1 scale
  configuration: `lite` (20 variants/family), `calibration` (40), and `publication` (150).
- Expanded generator validity reports with difficulty-stratum counts and causal fingerprints
  that include incident cause, remediation, topology, temporal transitions, and tier.
- Added a counterfactual oracle that forks a deterministic snapshot into correct-remediation,
  wrong-remediation, and wrong-target branches, then verifies divergent outcomes, replay
  determinism, restoration, and base-branch isolation.
- Added `validate-counterfactuals-v2` plus unit coverage for target-scale uniqueness, balanced
  tiers, monotonic structural controls, and the new generation profiles.
- Propagated non-answer-bearing tier, realization, seed/variant, depth, breadth, premise, event,
  and decision-context metadata into trial rows. Manifests record stratum counts, and steering
  reports now expose task success by family, difficulty tier, and condition.

## Validation result

A publication-shape rehearsal generated 450 scenarios: 150 per core family. Every family had
150 unique causal worlds, three equally represented structural/difficulty patterns, and a largest
template share of exactly one third. All 450 mechanical gold scenarios passed. All 300 unique
incident-backed worlds passed the counterfactual and snapshot-branch oracle.

The repository regression suite passes 132 tests with five credential-gated live adapter tests
skipped. Ruff reports no violations.

## Gate boundary

The implemented Phase D mechanics now satisfy the executable portions of Gate 2 at target shape,
but this is not a formal gate declaration while upstream specification/literature sign-off is
still open. The three patterns are procedural realizations from one generator implementation;
the independently authored realization requirement for the later core-suite phase remains open.
Difficulty strata are controlled structural interventions, not yet empirically calibrated model
difficulty. Live Mem0 and Zep validation remains intentionally deferred to final integration.
