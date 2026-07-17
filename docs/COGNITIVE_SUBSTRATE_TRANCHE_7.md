# Cognitive Substrate Tranche 7

Status: executable feature ablations and world-first uncertainty analysis implemented on
2026-07-17.

## Scope delivered

- Registered all nine required feature removals: provenance links, temporal metadata,
  evidence/claim distinction, stored intermediate conclusions, dependency tracking,
  supersession, active retrieval, lesson consolidation, and audit receipts.
- Added a representation-neutral single-feature ablation adapter. It transforms or suppresses
  canonical artifacts, relations, revision behavior, temporal queries, and declared capabilities
  while preserving the underlying adapter and scenario stream.
- Added policy-level tool removal for active retrieval and audit export. Agent-facing runs retain
  capture tools when retrieval alone is removed.
- Added `--ablation` to `run-cognitive-v2`. Manifests record the exact removed operations; trial
  rows distinguish `applied`, `no-condition-opportunity`, `no-scenario-opportunity`, and
  `unablated-control` cells.
- Added a deterministic hierarchical analysis whose primary unit is the scenario/world. It
  resamples structural templates, worlds, and then within-world observations while keeping family
  strata explicit.
- Paired effects match scenario, model, and repetition. Public hashes must agree across matched
  rows, preventing accidental comparison of different public worlds.
- Added full-system-versus-ablation effect intervals, task success by difficulty, recursive raw
  and trace-verified accuracy by derivation depth, bitemporal repair by difficulty, descriptive
  family/template/world variance, and condition-level missingness.
- Added `analyze-cognitive-v2`; `report-cognitive-v2` now embeds the hierarchical artifact and
  renders paired and ablation intervals in the steering report.

## Validation result

The repository suite passes 142 tests with five credential-gated live adapter tests skipped, and
Ruff reports no violations. Direct contract tests verify that each substrate ablation removes its
declared state or capability. An end-to-end matched rehearsal ran nine worlds under stateless and
automatic-passive control plus `no-temporal-metadata`, then produced deterministic nested-bootstrap
condition, depth, repair, variance, missingness, and ablation artifacts.

The deterministic provider showed a zero outcome delta for that rehearsal. This is expected to be
non-evidentiary: the run proves matching and analysis mechanics, not that temporal metadata lacks
value for real models or substrates.

## Gate boundary

Required ablation execution and nonparametric uncertainty plumbing now exist. Gate 4 remains open:
difficulty monotonicity, non-saturation, costs, and curves require representative model runs. The
mixed-effects formula is recorded as the pilot target but is not fitted here. Recursive
revision-by-depth still needs failure-amplification worlds with weakened or invalidated stored
conclusions. Lesson consolidation has no opportunity in the three current core families, so that
ablation is executable but analytically inapplicable until the rule/lesson track lands.
