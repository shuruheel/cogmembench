# Cognitive Substrate Upgrade: Tranche 1

Status: **Authorized for implementation on 2026-07-16.**

This is the separately scoped implementation tranche required by Section 26 of
`COGNITIVE_SUBSTRATE_UPGRADE_PLAN.md`. It starts Phase B foundations without claiming that Gate 0
or Gate 1 has passed.

## Scope

- Add backward-compatible schema-v2 event time (`event_time`) and report/transaction time
  (`report_time`) fields.
- Define the representation-neutral cognitive artifact, relation, interval, and audit-receipt
  models.
- Define the synchronous substrate adapter-v2 protocol, capability manifest, usage-reporting
  semantics, retrieval budgets, and dual-axis snapshots.
- Provide a deterministic native-clock reference adapter for contract testing.
- Preserve all schema-v1 fixtures and the existing MVP test suite unchanged.

## Explicitly out of scope

- Freezing the Gate 1 contract; this tranche produces the first executable draft.
- External adapters, network calls, or paid model runs.
- Scenario generators, evaluator changes, or publication-track claims.
- Changes to the existing MindGraph adapter before the generic contract tests are stable.

## Acceptance criteria

1. Schema-v1 fixtures load without migration.
2. Schema-v2 scenarios reject missing or non-monotonic report times.
3. The reference adapter demonstrates namespace isolation, idempotent writes, monotonic calls,
   bitemporal snapshots, revision history, bounded retrieval, audit export, and explicit usage
   fidelity.
4. The existing test suite and new contract tests pass under all supported Python versions.
