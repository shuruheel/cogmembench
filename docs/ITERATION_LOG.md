# Cognitive-v2 iteration disclosure log

Append-only. Record a new entry whenever observed outputs motivate a scenario, prompt, evaluator,
adapter, or analysis change. Never rewrite an older rationale after seeing publication results.

## 2026-07-16 — tool-policy smoke failures

Observed model families differed sharply in retrieval-tool use. This motivated explicit
agent-directed versus automatic-passive conditions, oracle capture, tool-policy metrics, and the
requirement for at least three materially different reasoning-model classes in calibration.

## 2026-07-16 — oracle pre-run contract failures

Pre-run gold checks exposed missing required-memory annotations and a provenance-target write bug
in the compatibility suite. The affected smoke protocol was versioned instead of mutated.

## 2026-07-17 — recursive repair weakness

The initial recursive family tested reuse but not amplification after a false premise. It was
extended with premise invalidation, a different corrected root cause/remediation on the same
service graph, superseding conclusion repair, budgeted repaired reuse, and stale-intrusion scoring.

## 2026-07-17 — plan-completion audit

The implementation audit found silent-zero risk in cost accounting and missing release/freeze
safeguards. Cost projection now reports unpriced components as unknown, and publication files now
require canaries, structural separation audits, and immutable hash freezes.
