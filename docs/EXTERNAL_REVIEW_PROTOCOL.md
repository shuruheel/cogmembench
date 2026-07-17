# External protocol and vendor review

No review listed here has been requested or completed yet.

## Independent protocol-review shortlist

The shortlist is role-based to avoid implying endorsement. Contact should use the public project
or corresponding-author channels linked from the literature matrix.

| Candidate group | Expertise sought | Conflict handling |
|---|---|---|
| LongMemEval maintainers | Multi-session temporal benchmark validity and abstention | Review method only; no adapter-system interest known |
| MemoryAgentBench or MemoryArena maintainers | Incremental memory agents, selective forgetting, action-based evaluation | Disclose overlapping benchmark positioning |
| TOKI author or an independent temporal-database researcher | Bitemporal clock/isolation semantics | Exclude anyone advising the target product from “independent” count |
| Evidence-tracing/provenance researcher | Decision receipts, late-evidence leakage, replay | Review audit schema and adversarial pairs |
| Benchmark measurement specialist | Statistical unit, power, multiplicity, human-agreement protocol | No product configuration review |

At least two completed reviews are sought before Gate 7, including one temporal/provenance reviewer
and one benchmark-design reviewer. Comments, dispositions, and protocol changes are committed as
append-only artifacts under `reviews/protocol/`.

## Review packet

Send the frozen draft protocol, literature matrix, schema/adapter contracts, one blinded scenario
per family, evaluator decision rules, adversarial cases, cost model, power plan, and the exact
questions below:

1. Is the novelty boundary accurate and appropriately narrow?
2. Are V/K clocks, invalidation, and decision-time evidence operationalized without leakage?
3. Can a non-graph system receive equal opportunity under the canonical contract?
4. Do the endpoints and statistical unit support the stated claims?
5. Which ambiguity, shortcut, or failure case would invalidate a primary conclusion?

## Vendor review window

Before publication execution, send each evaluated external system its adapter mapping, capability
manifest, pinned configuration, cost-accounting gaps, and a dry-run trace. Use one fixed 14-day
window. Record `accepted`, `changes_requested`, `declined`, or `no_response`; silence is never
reported as approval. Configuration changes after review require re-running portability and cost
audits and updating the freeze before any publication result exists.

The machine-readable registry is `configs/cognitive_v2_review_registry.json`. It starts in
`not_contacted` state and may only be updated from real correspondence.
