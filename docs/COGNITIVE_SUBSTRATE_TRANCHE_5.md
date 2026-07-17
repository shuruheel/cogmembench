# Cognitive Substrate Tranche 5

Status: mechanical Gate 2/3 validity controls implemented on 2026-07-17.

## Scope delivered

- Structural fingerprints for public lifecycle flow, bitemporal ledgers, derivation DAGs, and
  decision-context shape, independent of scenario IDs and domain wording.
- Two generator patterns per core family: optional bitemporal control observations, depth-3/4
  recursive DAGs, and two-/three-artifact decision contexts.
- Causal-world fingerprints, duplicate detection, template-concentration limits, and minimum
  unique-world ratios that prevent seed-label inflation.
- Public/evaluator leakage scans for internal artifact IDs and direct answers in checkpoint
  prompts; leakage is also included in gold-ceiling validation.
- Registered deterministic equivalence for bounded leading hedges, selected paraphrases,
  one-to-one list/scalar granularity, and equivalent remediation verbs, with explicit rejection
  of negation, ambiguity, and overbroad lists.
- Ten matched adversarial cases spanning all core families and both acceptance and rejection.
- Confidence requested at evaluated checkpoints, with coverage, Brier, and inappropriate-
  abstention diagnostics when the model supplies it.
- Additional temporal, recursive, retrieval, audit, provenance, and recomputation diagnostics
  that are mechanically supported by current traces.
- CLI validation artifacts via `validate-generators-v2` and `validate-evaluators-v2`.

## Validation result

The 15-scenario development suite has five unique public and causal worlds plus two structural
patterns per family, passes leakage checks, and retains a perfect oracle ceiling. The ten-case
evaluator corpus passes all expected accept/reject decisions. A 45-row suite produced by merely
repeating the fixed cases across three seed labels fails the causal-world-ratio check as intended.

## Gate boundary

This tranche does not claim Gate 2 or Gate 3. Target-scale generators must mint genuinely new
causal worlds rather than relabel fixed cases, and counterfactual oracle coverage remains partial.
Evaluator validity still requires a larger natural-language rationale corpus and independent,
blind human agreement. Mechanical equivalence rules are published controls, not substitutes for
human semantic judgment.
