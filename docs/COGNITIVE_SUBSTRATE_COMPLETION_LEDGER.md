# Cognitive Substrate 2.0 completion ledger

Updated: 2026-07-17

The credential-free implementation is complete. The machine-readable source of truth is
[`configs/cognitive_v2_completion.json`](../configs/cognitive_v2_completion.json). “Implemented”
means code, configuration, documentation, or validation machinery exists; it does not silently
promote an unexecuted scientific gate to “passed.”

## Mechanical closeout

The final credential-free rehearsal generated a fresh 450-scenario publication-shaped suite:
150 worlds per core family, balanced across easy, medium, and hard tiers. Gold, generator,
counterfactual, and release validations passed. Against a separately seeded development suite,
the publication candidate had zero overlap in public hashes, causal content, causal worlds,
structural fingerprints, and realization-pattern identifiers. Shared lexical n-grams are reported
but do not substitute for structural separation.
The compact evidence and artifact hashes are retained in
`results/aggregated/cognitive-v2-publication-rehearsal-20260717.json`; the multi-megabyte temporary
scenario files are intentionally not treated as a frozen publication dataset.

The release workflow embeds a canary in every scenario and writes an adjacent hash manifest. The
freeze workflow now verifies and hashes both the dataset and that passing release manifest. The
built-in publication realization pack is deliberately labeled implementation-team-authored; it
does not masquerade as the independently authored pack required for the final human-validity case.

## Phase status

| Phase | Credential-free implementation | Remaining exit dependency |
| --- | --- | --- |
| A — specification | Complete | Owner approval of Gates 0–1 |
| B — harness/skeleton | Complete | Live Mem0, Zep, and Cognee execution |
| C — first slice | Complete | Credentialed external development run |
| D — generators/environment | Complete; mechanical Gate 2 passes | None |
| E — evaluators/metrics | Complete | Independent blinded annotations for Gate 3 |
| F — suites/baselines/adapters | Complete | Live external matrix, empirical calibration, independently authored realizations |
| G — pilot/freeze | Tooling complete | Models, credentials, annotations, vendor review, frozen-pilot evidence |
| H — study/launch | Execution and analysis pipeline complete | Gate-ordered publication execution and launch |

## Irreducible deferrals

Credential- or endpoint-gated work:

- Live Mem0, Zep/Graphiti, and Cognee portability and full-protocol runs.
- Pinned representative-model calibration and the multi-model frozen pilot.
- Complete provider/server cost observations and empirical power inputs.
- The frozen held-out publication matrix and resulting fitted analyses.

External-human or publication acts, which are not responsibly automatable:

- Independent annotations and independently authored natural-language realizations.
- Named external protocol review and vendor configuration review.
- Owner signoff, the actual preregistration freeze, arXiv submission, and public launch.

Templates, blinded packets, scoring thresholds, review registry, immutable freeze machinery,
reproducibility instructions, and launch evidence requirements are implemented so these are
execution dependencies rather than missing engineering.
