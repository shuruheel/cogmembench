# Cognitive-v2 protocol specification

## Evaluation object

A cognitive substrate is evaluated as a stateful service that transforms a public, logically
timed event stream into durable cognitive artifacts and later makes bounded evidence available to
an otherwise fixed agent scaffold. The substrate is the treatment; the public world, model,
prompt/tool scaffold, budgets, and evaluation checkpoints are matched controls.

The scenario/world is the statistical unit. Sessions, retrieved items, questions, checkpoints,
and derivation nodes are repeated observations within that world and never inflate sample size.

## Primary questions and endpoints

| RQ | Question | Primary endpoint(s) |
|---|---|---|
| RQ2 | Does stored cognition enable later reasoning without replaying all premises? | `trace_verified_reuse_accuracy`; `trace_verified_repaired_reuse_accuracy` |
| RQ3 | Can the system reconstruct belief at valid time V using only knowledge available by K? | `belief_v_k_accuracy` |
| RQ4 | Does a changed premise trigger correct selective repair? | `dependency_invalidation_f1`; `unaffected_artifact_preservation_rate` |

Task success, audit fidelity, calibration, policy, ablation, and efficiency measures are secondary
or diagnostic unless a frozen manifest says otherwise.

## Required treatment cells

`stateless`, budget-matched `transcript`, `transcript-full` ceiling, `automatic-passive`,
`agent-directed-active`, and `oracle-passive`. Transcript and retrieval cells receive the same
read-context budget. A repetition recreates the namespace and repeats the full ingestion lifecycle.

The canonical reasoning scaffold is `canonical-v1`. A frozen subsample is repeated with the
semantically equivalent `minimal-v1` scaffold; manifests record the version and prompt hash, and
the robustness cells are analyzed separately rather than pooled.

Natural mode reports each substrate’s supported behavior. Matched mode fixes retrieval item/token
ceilings and the tested-agent scaffold. Unsupported instrumentation is `null`/capability-absent,
never zero.

## Clocks and evidence

`event_time` is valid time; `report_time` is transaction/logical time. A snapshot is selected by
both `valid_at` and `known_at`. The adapter clock never moves backward. Asynchronous systems must
quiesce before checkpoint reads. Audit evidence is admissible only when it is native or reversibly
mapped inside the tested service; harness sidecars cannot earn substrate credit.

## Analysis

Paired differences match scenario, model snapshot, and repetition. The nonparametric primary check
is a family-stratified template/world/observation nested bootstrap. The frozen mixed-effects target
is `treatment * depth_tier + treatment * model`, with random intercepts for world nested in
structural template nested in family. Multiplicity and minimum effects are frozen from a
non-publication pilot using `power-cognitive-v2`.

## Publication discipline

Publication worlds are created after iteration, canaried, and rejected if public hashes, causal
world fingerprints, structural fingerprints, or realization patterns overlap named development
references. Evaluators, conditions, prompts, model snapshots, exclusions, and analyses are then
hash-frozen with `freeze-cognitive-v2-protocol`. The freeze is immutable; corrections require a new
protocol ID and a disclosure entry.

Independent human relation/evaluator annotations must meet the preregistered κ and gold-majority
thresholds. Live adapter portability, multi-model calibration, vendor review, power finalization,
and publication execution are empirical gates, not properties inferred from code existence.
