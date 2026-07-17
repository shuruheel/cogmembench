# Cognitive Substrate Tranche 8

Status: recursive failure-amplification and revision-by-depth mechanics implemented on
2026-07-17.

## Scope delivered

- Every recursive world now includes a late forensic correction that rejects an actual ancestor
  premise of the stored conclusion.
- The corrected mechanism uses a different root service, cause, signal, and remediation over the
  same public service graph. This isolates conclusion repair from an unrelated environment swap.
- Added `repair` and `reuse_repaired` checkpoints after initial derivation and reuse. The second
  reuse remains budget-asymmetric, so raw diagnostic re-derivation does not count as repaired
  cognitive reuse.
- Hidden controls identify the invalidated premise, stale conclusion, revised conclusion, and
  revision depth. The revised expected memory explicitly supersedes the original conclusion.
- The oracle revises both the invalidated premise and conclusion in logical time, retrieves only
  the revised conclusion under the reuse budget, and executes the corrected incident world.
- Added conclusion-revision accuracy, raw and trace-verified repaired reuse, revised-conclusion
  retrieval, stale-conclusion intrusion, and failure-amplification-avoidance metrics.
- Added a recursive revision-by-depth curve alongside the existing accuracy-by-depth curve in the
  world-first hierarchical analysis.
- Expanded the adversarial evaluator corpus with a stale-conclusion-after-invalidation rejection
  case.

## Validation result

The 450-scenario publication-shape rehearsal remains valid. All 150 recursive worlds perfectly
revised and reused the corrected conclusion under the oracle, with zero stale-conclusion
intrusion. All 450 gold scenarios, 450 initial/corrected incident counterfactual worlds, generator-diversity gates,
and all 11 evaluator-adversarial cases pass.

A three-depth agent-facing rehearsal completed 15/15 trials across stateless, matched transcript,
automatic passive, agent-directed active, and oracle conditions. It emitted depth-3/4/5 revision
curves; the oracle reached 1.0 trace-verified repaired reuse at every depth, while the deterministic
automatic-capture probe reached 0.0. That contrast is a harness localization result, not a model or
product claim.

The repository suite passes 144 tests with five credential-gated live adapter tests skipped.
Ruff and diff checks pass.

## Gate boundary

Accuracy-by-depth and revision-by-depth now have executable world, trace, metric, and uncertainty
contracts. Gate 4 still requires representative models, repeated full-lifecycle runs, monotonicity
and saturation checks, and a measured cost/power decision. The current correction realization
uses one forensic-invalidity pattern; independently authored and lexically broader realizations
remain required before publication freeze.
