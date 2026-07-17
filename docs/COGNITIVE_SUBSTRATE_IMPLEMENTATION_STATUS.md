# Cognitive Substrate Implementation Status

Updated: 2026-07-17

This status separates implemented code from validation-gate claims. No gate passes merely because
the corresponding interface exists.

## Implemented

- Schema-v2 public events with stable IDs, lifecycle phases, valid/event time, and
  report/transaction time; schema-v1 serialization and public hashes remain compatible.
- Canonical cognitive artifact, relation, time-interval, and audit-receipt models.
- Representation-neutral adapter-v2 protocol with clock modes, quiescence, namespace isolation,
  dual-axis snapshots, bounded retrieval, capability manifests, and explicit usage fidelity.
- Deterministic native-clock reference adapter with idempotent commits/revisions, historical
  snapshots, lineage relations, retrieval traces, and decision-time audit filtering.
- Flat canonical-text Okapi BM25 baseline using fixed parameters and temporal/relation metadata;
  audit export is explicitly capability-absent.
- Rolling extractive summary, standalone vector, and BM25/vector RRF hybrid adapters over the
  same canonical rendering, with ranking-leg traces and complete harness-side embedding usage.
- Event-sourced hidden world ledger and deterministic procedural bitemporal belief-revision
  generator with seeded causal values and three controlled realization tiers.
- Phase-driven oracle-capture executor and deterministic RQ3/RQ4 evaluator for
  `belief(V, K)`, dependency-invalidation F1, and unaffected-artifact preservation.
- Deterministic service-incident environment with seeded parameterized causal mechanisms,
  tiered dependency topologies, costly probes and remediations, execution scoring, replay,
  snapshots, and isolated counterfactual branches.
- Recursive-investigation generator with mechanical derivation DAG depth/breadth, budget
  asymmetry, premise dispersion, trace-verified conclusion reuse, and environment execution.
- Decision-lineage generator and oracle evaluator with harness-logged decision context,
  action/outcome lineage, rationality scoring, and matched faithful/contaminated audit receipts.
- CLI generation, reusable adapter conformance audits, and mechanical gold-ceiling validation.
- Agent-facing five-treatment executor plus a full-transcript ceiling, with balanced scheduling,
  automatic passive context, standardized active tools, genuinely budget-matched transcript
  replay, fresh namespaces, and complete observable model/tool/retrieval traces.
- Representation-neutral outcome-track scorers for all three core families, with backend
  instrumentation reported as available/unavailable rather than silently scored as zero.
- Cognitive-v2 runner and manifest with scenario/schedule hashes, condition contracts, adapter
  capability and usage reports, raw and evaluated JSONL, and deterministic CI support.
- Steering reports with per-family treatment cells, capture-mode failure localization,
  longitudinal score deltas, regression/improvement lists, and capability-manifest changes.
- External adapter kit with native/mapped/sidecar evidence declarations, remote append-only
  canonical journals, capability-aware portability audits, and live-test selection.
- Mapped walking-skeleton adapters for MindGraph public HTTP, self-hosted Mem0 OSS REST, and Zep
  Cloud Graph API v2. The adapters are accepted by the cognitive-v2 runner and CLI.
- External cognitive-v2 runs require a passing portability audit before scheduling any trial and
  embed the declared-versus-observed audit result in the run manifest.
- Local BM25, summary, vector, and hybrid runs use the same mandatory preflight; all four pass the
  contract, isolation, reset, temporal snapshot, relation, and accounting probes in CI.
- A deterministic three-family smoke completed 12/12 valid automatic-passive trials across those
  four local adapters with matched scenario, schedule, item, and read-token budgets.
- Structural fingerprints now distinguish lifecycle, ledger, and derivation topology from domain
  wording. Each family has three patterns across unbounded procedural causal worlds, with guards for
  duplicate rows, template concentration, causal-world reuse, internal-ID leakage, and direct
  checkpoint-answer leakage.
- An eleven-case matched adversarial evaluator corpus accepts bounded hedging, registered paraphrases,
  equivalent one-item granularity and valid remediation wording while rejecting stale beliefs,
  overbroad answers, unsupported reuse, and post-hoc evidence.
- Added mechanically supported stale-intrusion, supersession, snapshot-isolation, downstream
  repair, retrieval precision/recall, unsupported-inference, recomputation, source-attribution,
  temporal-provenance, minimal-support, replay, abstention, and confidence-coverage diagnostics.
- A real disposable MindGraph 1.9.0 HTTP execution passed that mandatory preflight and all six
  automatic-passive/agent-directed-active trials across the three-family smoke suite.
- Cognitive-v2 generation profiles now cover smoke, development, lite, calibration, and a
  450-scenario publication shape without modifying locked schema-v1 scale definitions.
- A publication-shape mechanical rehearsal produced 150 unique causal worlds per family with
  exactly balanced easy/medium/hard tiers; all 450 gold oracles and all 450 initial/corrected
  incident counterfactual/snapshot branch validations passed.
- Runner rows and manifests retain safe difficulty/realization controls, and steering reports
  aggregate task success by difficulty and condition so calibration does not require hidden-world
  answer joins.
- All nine required single-feature ablations have explicit contracts. Canonical substrate
  removals alter stored state/capabilities, policy removals alter available tools, and runner rows
  distinguish applied, inapplicable, and unablated control cells.
- World-first hierarchical analysis provides nested bootstrap intervals, matched treatment and
  ablation deltas, difficulty/depth/repair summaries, variance components, missingness, and a
  preregistered mixed-effects target formula.
- Recursive worlds now invalidate a required ancestor premise after initial conclusion reuse,
  require a superseding conclusion for a different causal mechanism on the same service graph,
  and score trace-verified repaired reuse, stale intrusion, and failure-amplification avoidance by
  derivation depth.
- Cognee joins Mem0 and Zep as a mapped external adapter, with a dataset-scoped lifecycle,
  multipart ingestion, blocking cognification, lexical retrieval, exact remote reconstruction,
  fake-service tests, configuration, and opt-in live test.
- The verified literature matrix tests the narrow joint novelty claim against primary artifacts;
  the protocol and reviewer registry define the external review and response process without
  fabricating outreach.
- Lifecycle cost projection, paired-world power analysis, confidence calibration, and the staged
  failure taxonomy are executable reports. Unknown external costs remain explicit lower bounds.
- Release preparation embeds one canary in every scenario and records public, causal-content,
  causal-world, structural, realization, and lexical overlap. The publication holdout pack changes
  both structure and realization while explicitly recording that it is not independently authored.
- Blinded relation-annotation packets keep answer keys separate; agreement scoring reports Fleiss'
  kappa, majority gold accuracy, preregistered thresholds, missing items, and pass/fail status.
- Immutable protocol freezes record repository state and hashes for scenarios, their verified
  passing release manifest, configurations, prompts, evaluators, runners, model snapshots,
  endpoints, exclusions, and analysis rules; verification detects later drift.
- The reproducibility package, external adapter kit, review protocol/registry, iteration log,
  lite profile, Apache-2.0 code license, and CC BY 4.0 dataset license are present.
- A separately seeded 450-world release rehearsal passed all mechanical validations and had zero
  public-hash, causal-content, causal-world, structural-fingerprint, and realization-pattern
  overlap with development.

## Gate boundary

| Gate | Current evidence status | What prevents a formal pass |
| --- | --- | --- |
| 0 | Literature and scope artifacts ready | Owner governance signoff |
| 1 | Contracts, endpoints, unit, and cost model ready | Owner formal freeze/signoff |
| 2 | Mechanical criteria pass at publication shape | Nothing mechanical |
| 3 | Gold and adversarial criteria pass | Independent blinded human agreement |
| 4 | Calibration/cost/power machinery ready | Representative pinned-model observations |
| 5 | Local/reference and live MindGraph evidence pass | Live external full-protocol evidence |
| 6 | Failure, cost, and power tooling ready | Frozen multi-model pilot and human/vendor inputs |
| 7 | Release and immutable-freeze tooling ready | Gate 6 and the actual owner-authorized freeze |
| 8 | Held-out runner and analyses ready | Execution after the real Gate 7 freeze |

## Deferred execution

Live Mem0, Zep, and Cognee evidence; pinned-model calibration/pilot runs; complete provider/server
costs; empirical power; and publication execution remain credential- or endpoint-gated. Independent
annotations, independently authored realizations, named external review, vendor review, owner
signoff, arXiv submission, and launch are external-human acts. Their packets, registries,
thresholds, and procedures are implemented, but no result or approval is claimed before it exists.

The detailed phase/deliverable mapping is in
`configs/cognitive_v2_completion.json` and `docs/COGNITIVE_SUBSTRATE_COMPLETION_LEDGER.md`.
