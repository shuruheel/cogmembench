# Task Families

## Cognitive Substrate 2.0 core

The first implemented core slice is `bitemporal_belief_revision`. It generates a hidden,
event-sourced ledger with valid time and transaction time, a belief-derived decision, a
retroactive correction, dependency invalidation, an unaffected constraint, and current plus
historical `belief(V, K)` probes. Its deterministic reference path is a validation ceiling, not
product evidence.

The second implemented family is `recursive_investigation`. Its seeded service-incident worlds
have executable probes and remediations, derivation DAGs, explicit depth and breadth, dispersed
premises that exceed the reuse read budget, and trace-verified reuse of a stored conclusion.

The third implemented family is `decision_lineage`, covering contemporaneous support,
alternatives, assumptions, actions, outcomes, rationality, and post-hoc evidence leakage. Its
generator mints matched faithful and contaminated audit receipts for deterministic evaluator
validation.

All three families can be executed under the cognitive-v2 treatment matrix. Outcome scoring is
separate from instrumented substrate scoring so representation-specific capability gaps do not
become false task failures. Family-level treatment deltas feed the iteration steering report.
Development validation requires distinct causal worlds and at least three controlled structural
and difficulty patterns per family, bounded template concentration, no public/evaluator leakage,
a perfect mechanical oracle ceiling, and the matched evaluator-adversarial corpus. The generators
now support 20-world lite, 40-world calibration, and 150-world-per-family publication profiles;
causal parameters and topologies vary with seed and variant rather than being relabeled fixtures.

Incident-backed families also pass a mechanical counterfactual oracle: correct, wrong-detail,
and wrong-target interventions fork from the same snapshot, outcomes must diverge, and replay,
restoration, and base-branch isolation must hold.

Single-feature cognitive-v2 runs can remove each feature required by Section 16.2 of the upgrade
plan. Ablation rows are analytically eligible only when the selected family and persistent
treatment expose that feature. Combined evaluated files are paired by public-world hash, scenario,
model, and repetition before producing an ablated-minus-full effect.

Hierarchical reporting treats the world as the primary unit, resampling templates, worlds, and
then within-world observations. It reports difficulty and derivation-depth curves without treating
checkpoints as independent samples.

Recursive worlds now measure both accuracy-by-depth and revision-by-depth. After initial reuse, a
late correction rejects a required premise; successful repair must supersede the stale conclusion,
retrieve the revised conclusion under the same asymmetric budget, and execute the corrected causal
world. The calibration, paired power, cost, and hierarchical-analysis paths are implemented;
representative-model observations remain deferred until pinned live credentials are available.

The plan-wide engineering status is tracked in `configs/cognitive_v2_completion.json`. Remaining
core-suite work is execution rather than generator construction: live external adapters,
representative models, independent annotations/realizations, and the gate-ordered publication run.

Post-core tracks are project cognition, counterfactual branching, and rule/lesson induction.
The human-authored realism suite remains contingent on post-launch feedback.

## MVP compatibility families

The schema-v1 compatibility generators retain four multi-session families.

`preference_continuity` introduces an explicit preference, a conditional exception, noise,
and a later correction. Evaluation checks the active value and rejects the superseded value.

`belief_revision` introduces a sourced claim, weaker corroboration, contradictory/corrective
evidence and a scoped final truth. Evaluation checks current belief, confidence language,
stale-claim suppression and provenance.

`project_continuation` creates an objective, dependencies and decisions, records completion
and failure, changes a requirement, then asks for the next executable action. Evaluation uses
hidden task state rather than plan fluency.

`failure_learning` records an attempted method, failure cause and applicability boundary,
then presents a similar case and an unrelated control. Evaluation rewards transfer without
overgeneralization.

These families remain regression/integration fixtures. They are not expanded into the cognitive
v2 publication suite and must not be described as the benchmark's future publication scope.
