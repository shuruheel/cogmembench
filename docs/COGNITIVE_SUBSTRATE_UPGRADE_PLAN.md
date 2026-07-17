# CogMemBench Cognitive Substrate Upgrade Plan

Status: **Credential-free implementation complete (2026-07-17); scientific gates and
publication execution remain governed by Sections 20–22.**

Implementation evidence is indexed in `configs/cognitive_v2_completion.json` and
`docs/COGNITIVE_SUBSTRATE_COMPLETION_LEDGER.md`. This plan still does not authorize skipping a
validation gate or treating a mechanical rehearsal as scientific evidence.

Working designation: **CogMemBench 2.0 — Cognitive Substrate Evaluation**

This plan upgrades CogMemBench from a cross-session memory benchmark into a
treatment-controlled benchmark of how well a persistent memory solution serves as a cognitive
substrate for an AI agent.

Revision note: v2 incorporates the 2026-07-16 design review. It reframes the benchmark's primary
purpose as a longitudinal product-iteration instrument (Section 2), resolves first-release scope
decisions (Section 25), fixes four technical design holes identified in review (clock discipline,
re-derivation confounding, audit-faithfulness operationalization, adapter contract gaps), adds
governance and budget machinery, and re-sequences delivery around an early vertical slice. The v1
draft is preserved outside the repository for diffing.

## 1. Benchmark identity

CogMemBench should primarily benchmark the **preservation, reuse, revision, temporal
reconstruction, and auditability of explicit cognitive state**. It should not primarily benchmark
raw conversational recall, generic model intelligence, or affinity with a particular storage
representation.

The central thesis is:

> A useful cognitive substrate must do more than retrieve past text. It must preserve evidence,
> derived beliefs, decisions, intentions, actions, outcomes, and their temporal and causal
> relationships; make them available for later reasoning; revise affected cognition when the world
> changes; and support faithful reconstruction of how earlier knowledge influenced later action.

The benchmark should operationalize the "hippocampus for AI" analogy through functions rather
than claims of biological equivalence. Relevant functions include rapid episodic binding,
relational association, temporal context, pattern separation, pattern completion, replay,
reconstruction, consolidation, prospective intention, and simulation from prior states. Because
HippoRAG and successors already occupy the hippocampal-indexing framing in the retrieval
literature, the positioning must engage that work explicitly and differentiate on lifecycle
functions (revision, temporal reconstruction, audit) rather than on the analogy itself.

### 1.1 Primary purpose and posture

Resolved 2026-07-16: the benchmark is, first, the **decisive instrument for iterating MindGraph
toward the cognitive-substrate vision**, and, jointly, a **credibility and visibility artifact for
AI researchers**. These are co-primary. The second is only achievable if the benchmark is
excellent enough that researchers would cite it from an arXiv posting and social distribution
alone; formal peer review is optional and must never gate the benchmark itself.

Consequences of this posture, threaded through the rest of the plan:

- The benchmark runs repeatedly against evolving MindGraph versions; it is a longitudinal
  instrument, not a one-shot study (Section 2).
- Per-feature causal attribution (ablations, capture-mode deltas, failure localization) is the
  primary product deliverable. The cross-system comparative study is the publication deliverable.
- Generator, evaluators, harness, and adapters are published; anyone can re-mint held-out worlds
  and reproduce results. The artifact must persuade without a referee.
- Venue mechanics (preregistration registries, submission formats, journal-grade multiplicity
  machinery) are right-sized to what credibility actually requires (Sections 18, 20).

### 1.2 Intended contribution

The intended contribution is the joint evaluation of:

1. Recursive reuse of conclusions derived in earlier episodes.
2. Bitemporal reconstruction of world state and agent knowledge state.
3. Propagation of corrections through dependent beliefs, decisions, plans, and policies.
4. Evidence and execution provenance from sources through actions and outcomes.
5. Consequential downstream task performance under controlled memory treatments.
6. Lifecycle efficiency and policy quality, not only final-answer accuracy.

The benchmark should be positioned as a **diagnostic causal protocol** rather than another broad
long-conversation question-answering dataset. The launch narrative is a **cross-system
failure-mode map** — where every measured system, including MindGraph, breaks — not a product
victory claim.

### 1.3 Non-goals for the first release

The first release should not make the following primary objectives:

- Biological fidelity to the human hippocampus.
- Evaluation of private chain-of-thought quality.
- General computer-use intelligence.
- Multimodal memory.
- Large-scale multi-agent coordination.
- Privacy and access-control benchmarking.
- A single leaderboard score that conceals different failure modes.
- Demonstrating that graphs are inherently superior to flat, vector, relational, neural, or
  event-sourced representations.

These can become later tracks if the core benchmark succeeds.

## 2. Longitudinal iteration protocol

This section is new in v2 and reflects the benchmark's primary purpose.

### 2.1 Two-track operation

The benchmark operates on two permanently separated tracks:

- **Iteration track.** Development-scale runs on development worlds, executed on a regular
  cadence (target: every MindGraph minor release, or monthly, whichever comes first). Prompts,
  evaluators, and scenarios may evolve between runs; every change is logged (Section 2.4).
  Budget target: ≤ ~$2,500 model spend per run.
- **Publication track.** Frozen protocol, freshly generated held-out worlds, full condition
  matrix, published results. Governed by the publication-discipline gates (Section 21).

Iteration-track results steer the product and are publishable only as explicitly labeled
development evidence, never as benchmark claims.

### 2.2 Steering reports

Every iteration-track run produces a steering report containing:

- Failure localization by pipeline stage (capture → organization → retrieval → interpretation →
  reasoning → action), using capture-mode deltas (Section 7).
- Ablation deltas mapped to substrate features (Section 16.2) — each ablation is a roadmap
  experiment answering "should MindGraph invest in this feature."
- Regressions and improvements against the previous MindGraph version, per metric family.
- Capability-manifest changes (Section 6.3).

### 2.3 Regression tracking

Every run records the tuple (benchmark protocol version, world-set version, harness commit,
product version, model snapshot). A longitudinal results table accumulates across product
versions so score movements are attributable. The existing manifest machinery (repository SHAs,
config hashes, protocol locks) already supports this and is retained.

### 2.4 Goodhart defenses

A benchmark iterated against stops being decisive evidence unless the following hold:

- **Fresh-world publication rule.** Any published claim runs on worlds generated after the
  publication freeze that were never used during iteration. The controlled generator's ability to
  mint unlimited structurally held-out worlds is the primary contamination and Goodhart defense,
  and the protocol commits to it explicitly.
- **Iteration disclosure log.** The existing practice of disclosing benchmark-development changes
  prompted by observed outputs (currently in LIMITATIONS.md) continues as a dedicated append-only
  iteration log. Every evaluator, prompt, or scenario change motivated by a run is recorded.
- **Canary and contamination checks.** A canary GUID is embedded in every published dataset file;
  published worlds carry n-gram overlap checks against future training-data claims.
- **Structural holdout.** Publication worlds differ from iteration worlds in causal structure,
  domain realization, and lexicalization — not merely in random seed (Section 15.5).

## 3. Research positioning

Before freezing the protocol, complete and publish a structured literature comparison. Two rules
govern it:

1. **Verify the artifact, not the citation.** Every compared benchmark must be confirmed against
   its actual paper, dataset, and code — capabilities checked empirically where cheap. No entry
   may rest on a name remembered from a survey.
2. The audit must **test, rather than assume, the novelty claim**.

At minimum, compare CogMemBench with:

- LongMemEval: multi-session reasoning, updates, temporal reasoning, and abstention.
- MemoryAgentBench: retrieval, test-time learning, long-range understanding, and selective
  forgetting.
- MemoryArena: interdependent multi-session agent-environment tasks.
- BEAM: long-conversation memory evaluation (named in the credible set by our own claim policy).
- HippoRAG and successors: hippocampal-indexing framing for retrieval — required engagement for
  the Section 1 analogy.
- Zep / Graphiti's temporal knowledge-graph evaluation work: the closest conceptual rival on
  validity intervals and edge invalidation.
- Mem0, Letta/MemGPT, A-MEM and other deployed memory systems' self-published evaluations —
  compared as measurement approaches, and noting where (as with LoCoMo) the underlying dataset is
  considered discredited.
- EvolMem and EvoMemBench: cognitive dimensions and self-evolving memory.
- STALE: implicit invalidation and stale-premise resistance.
- TOKI: bitemporal contradiction handling and audited provenance.
- PM-Bench: prospective memory and delayed intentions.
- EMemBench and REMem: episodic recollection and reasoning.
- Work on evidence tracing, execution provenance, and auditable agent traces.

The novelty claim to test is that no existing benchmark jointly asks:

1. What was believed at valid time `V` given information known by transaction time `K`?
2. Which contemporaneously available evidence supported a derived conclusion or decision?
3. When a premise changes, which downstream cognitive artifacts are invalidated or weakened?
4. Can repaired cognition support later reasoning and action across increasing recursive depth?
5. Can an auditor distinguish a faithful decision-time rationale from post hoc rationalization?

If another benchmark already covers this intersection, revise the contribution before building the
publication suite.

## 4. Primary research questions

The protocol preregisters (via time-stamped repository hash; see Section 20) a small set of
primary research questions, each with one or two designated primary endpoints. All other metrics
in Section 17 are exploratory or diagnostic.

| RQ | Question | Primary endpoints |
| --- | --- | --- |
| RQ1 Cognitive substrate value | Under a fixed reasoning model and task stream, how much does each memory treatment improve later reasoning and action relative to stateless, transcript, summary, and retrieval baselines? | Paired task-success delta vs. budget-matched transcript; execution success in the environment family |
| RQ2 Recursive reasoning | How does performance change as later decisions depend on deeper, wider, and more temporally separated chains of previously derived cognition? | Trace-verified reuse-dependent accuracy by derivation depth (curve, not mean) |
| RQ3 Temporal cognition | Can the substrate distinguish what was true, what was reported, what was known, and what was believed at different times? | `belief(V, K)` reconstruction accuracy (valid-time and known-at components) |
| RQ4 Revision and dependency repair | When a premise is corrected, retracted, or implicitly invalidated, does the substrate update the right dependent artifacts while preserving unaffected history? | Dependency-invalidation F1; unaffected-artifact preservation rate |
| RQ5 Decision auditability | Can the substrate reconstruct the evidence, assumptions, alternatives, and constraints actually available when a decision was made? | Decision-time context reconstruction F1; post hoc evidence leakage rate |
| RQ6 Cognitive policy | How well does the agent-substrate combination decide what to store, relate, retrieve, revise, consolidate, and leave uncertain? | Write-appropriateness F1; retrieval-appropriateness F1 |
| RQ7 Lifecycle efficiency | What performance is obtained per token, model call, unit of latency, unit of storage growth, and estimated cost? | Cost per successful task; task success per 1k read-context tokens |

## 5. Canonical cognitive lineage ledger

Every scenario should have a hidden, immutable, event-sourced ground-truth ledger. This ledger is
an evaluator model, not a required internal ontology for tested systems.

### 5.1 Artifact layers

| Layer | Core artifacts | Purpose |
| --- | --- | --- |
| World | Source, observation, event | Represent what occurred and where reports came from |
| Epistemic | Evidence, claim, hypothesis, conclusion, assumption, open question | Represent what the agent could justifiably believe |
| Intentional | Goal, constraint, option, decision, plan, deferred intention | Represent how cognition guides future behavior |
| Experiential | Action, execution, outcome, failure | Represent attempts and environmental feedback |
| Consolidated | Lesson, rule, policy | Represent reusable knowledge derived from experience |

The initial implementation may use a common `CognitiveArtifact` envelope with a typed payload
rather than a large class hierarchy.

### 5.2 Required artifact fields

The canonical envelope should support:

- Stable artifact ID.
- Artifact kind.
- Natural-language and structured content.
- Entity and scenario scope.
- Valid-time interval: when the artifact applies in the world (logical scenario time; see
  Section 11.3).
- Transaction-time interval: when it was present in the agent's knowledge state (logical scenario
  time).
- Epistemic status such as proposed, accepted, uncertain, rejected, stale, or superseded.
- Optional confidence, with calibration evaluated separately from correctness (Section 17.8).
- Creating actor and session/turn.
- Direct public-event provenance.
- Version or revision lineage.
- Visibility classification for leakage control.

### 5.3 Required relations

Keep the core relation vocabulary small and semantically testable:

- `supports`
- `contradicts`
- `derived_from`
- `depends_on`
- `supersedes`
- `motivates`
- `implements`
- `produces`
- `learned_from`
- `applies_to`
- `invalidates`

Relations may carry temporal scope, strength, source, and creation metadata. A system receives no
credit merely for producing a relation; the relation must be semantically and temporally correct.
Because several relations overlap in ordinary usage (`derived_from` vs. `depends_on`;
`contradicts` vs. `invalidates` vs. `supersedes`), the specification must include annotation
decision rules with measured inter-annotator agreement, or relation precision/recall will be
noise (Gate 3).

### 5.4 No private chain-of-thought requirement

The benchmark must never require hidden chain-of-thought. "Reasoning capture" means explicit,
externally meaningful artifacts such as claims, assumptions, alternatives, constraints, decisions,
rationales, open questions, outcomes, and lessons. Traces should record observable model outputs,
tool calls, retrieved context, and artifact operations only.

## 6. Representation-neutral evaluation tracks

### 6.1 Outcome track

Treat the memory solution as a black box. Score task success, recursive reasoning, temporal
reasoning, revision, transfer, prospective behavior, robustness, and efficiency. The system need
not expose nodes or edges.

### 6.2 Instrumented substrate track

Require a canonical export of cognitive artifacts, provenance receipts, temporal metadata, and
dependency claims. Internally, a system may use documents, vectors, relational tables, graphs,
event logs, neural state, or hybrids.

The normalized audit receipt should be capable of expressing:

- The cognitive artifact or decision being explained.
- Evidence and intermediate artifacts used.
- Original public source events.
- Memories retrieved before the decision.
- Decision and retrieval timestamps.
- Assumptions and alternatives, when explicitly recorded.
- Later revisions without contaminating the original decision-time view.

### 6.3 Capability reporting

Unsupported advanced operations must be reported as unsupported, not silently converted into an
incorrect answer or a degraded treatment. Reports should distinguish:

- Capability absent.
- Capability present but incorrectly executed.
- Capability present but not invoked by the agent.
- Infrastructure failure.

Each adapter publishes a **capability manifest** (including its clock mode, Section 11.3;
snapshot support; branching support; usage-reporting fidelity).

**Analysis semantics.** Capability-absent cells are excluded from paired comparisons for the
affected metrics and shown in a coverage matrix; they are never imputed as zero or as failure.
**Anti-gaming guard:** where a probe can be executed mechanically regardless of the declaration,
the harness runs it anyway and reports declared vs. observed capability; declarations are also
checked against the system's public documentation. A system may not dodge a hard probe by
declaring it unsupported when its documentation advertises the capability.

## 7. Capture and retrieval treatments

Every compatible substrate should be evaluated in three capture modes where possible.

### 7.1 Automatic capture

The system receives the ordinary public interaction stream and decides what to preserve, how to
represent it, and how to revise it. This evaluates the complete deployed memory solution.

### 7.2 Agent-directed capture

The fixed reasoning agent receives standardized cognitive operations for recording observations,
claims, decisions, outcomes, lessons, revisions, relations, and retrievals. This evaluates the
combined substrate affordance and cognitive-tool policy. The operation set is defined
benchmark-side (Section 8); mapping operations onto each substrate is the adapter's job.

### 7.3 Oracle capture

The harness writes correct artifacts, metadata, and relations at their annotated transition
points. The system must retrieve, reconstruct, revise, and apply them. Oracle capture must exist
for flat and vector systems too, using a **fixed, shared canonical text rendering** plus IDs and
metadata — the rendering is one artifact of the protocol, not tuned per system, and its adequacy
is validated by the oracle-retrieval ceiling check at Gate 4.

Together, these modes support failure localization:

```text
capture -> organization -> retrieval -> interpretation -> reasoning -> action
```

If automatic capture fails but oracle capture succeeds, the main deficit is upstream. If oracle
capture fails, the deficit lies in retrieval, temporal representation, interpretation, or use.
This decomposition is the core mechanism behind iteration-track steering reports (Section 2.2).

### 7.4 Matrix restraint

Capture modes need not cross fully with every other factor. Automatic capture runs for all
systems; agent-directed capture runs for systems exposing operations; oracle capture runs for all
compatible systems. Retrieval-policy crossings (passive prefetch vs. active pull) are required
only on the target system and at least one external system; elsewhere they are exploratory. The
publication matrix is fixed at Gate 6 within the budget envelope (Section 15.6).

## 8. Standard substrate adapter

Design a generic adapter contract before adding new systems, and validate it against real
external systems in the walking skeleton (Section 22, Phase B) — not for the first time at
Phase F. The provisional surface is:

```python
# lifecycle
reset(namespace)                          # verified by sentinel contamination probes
quiesce()                                 # barrier: all asynchronous ingestion, indexing, and
                                          # background writes observably complete
close_session(session_id, logical_time)

# capture
observe(event, logical_time)              # automatic-capture input stream
commit(artifact, logical_time)            # agent-directed / oracle capture
revise(artifact_id, revision, logical_time)
link(source_id, relation, target_id, logical_time)

# use
retrieve(query, budget, logical_time, valid_at=None, known_at=None)
snapshot(valid_at=None, known_at=None)    # the belief(V, K) surface — both axes, independently
export_audit(decision_ref)

# accounting and capability
usage_report()                            # tokens, calls, embedding usage — including
                                          # substrate-internal LLM calls, or an explicit
                                          # 'unavailable' declaration; never silent zeros
capability_manifest()                     # clock mode, snapshot, branching, usage fidelity, ...
```

Optional time-travel operations (advanced track):

```python
branch(snapshot_id)
merge(branch_id)
discard(branch_id)
```

Contract notes, several forced by observed failures in the current harness:

- `snapshot` exposes **both** temporal axes. v1's single `as_known_at` parameter conflated valid
  time and transaction time and left the benchmark's core query without a surface.
- `quiesce` is mandatory. The current MindGraph adapter has already hit two async-ingestion races
  (a wiki-autocompile write landing after `/clear` returned; an in-flight auto-embedding
  recreating an orphan row post-reset). Reset verification and session boundaries must be able to
  await a quiesced substrate.
- `usage_report` must cover substrate-internal model usage or explicitly declare it unavailable.
  RQ7 is unanswerable otherwise; today MindGraph's own server-side extraction cost is invisible
  and every such cell must be labeled a lower bound.
- The contract must also specify idempotency, isolation, error semantics, reset verification,
  namespace behavior, maximum context returned, and how asynchronous ingestion becomes
  observable. Product-specific adapters must remain outside evaluator code.

## 9. Scenario lifecycle

A complete scenario may contain the following phases:

1. **Accumulate:** observe events, sources, evidence, goals, and constraints.
2. **Derive:** form intermediate claims, hypotheses, or conclusions.
3. **Decide:** choose an action using the current epistemic state.
4. **Experience:** execute the action and receive an outcome.
5. **Consolidate:** derive a lesson, rule, or revised policy.
6. **Reuse:** apply prior cognition to a later related problem.
7. **Perturb:** introduce correction, contradiction, delayed evidence, or a changed requirement.
8. **Repair:** update affected cognition without erasing valid history.
9. **Audit:** reconstruct an earlier decision and its contemporaneous basis.
10. **Time travel:** query or branch from an earlier epistemic state.

Publication scenarios should combine multiple phases. **Single-phase diagnostic probes are a
permanent first-class tier**, not a temporary scaffold: they form the unit-test suite that runs
in CI and on the iteration cadence, and they are what localizes a regression to a phase. They do
not dominate the publication suite, but they are maintained and versioned with the same rigor.

## 10. Recursive reasoning design

Define recursive reasoning as a setting in which an explicit artifact derived during one episode
is necessary input to reasoning in a later episode.

The hidden ground truth should contain dependency DAGs rather than only chains. **Depth is
defined** as the longest path of required derivation inputs from source evidence to the queried
artifact; breadth as the number of required inputs at the widest layer. Both are reported.

Controlled factors should include:

- Derivation depth.
- Branching and convergence.
- Number of competing hypotheses.
- Number of supporting and defeating premises.
- Temporal distance between derivation and reuse (in logical scenario time).
- Lexical distance between creation cue and reuse cue.
- Distractor density.
- Reuse frequency.
- Whether a premise is later weakened or invalidated.
- Whether an induced rule applies to a later case.
- **Re-derivability** (new in v2; see below).

### 10.1 The re-derivation confound

A strong reasoning model can often ignore stored conclusions and re-derive them from raw
evidence, making "reuse of derived cognition" indistinguishable from "solved it again." Without a
control, RQ2's depth curves partly measure model reasoning rather than the substrate. Two
mechanisms control re-derivability:

- **Budget asymmetry:** at reuse time, the raw premises collectively exceed the read-context
  budget by a controlled factor while the derived conclusion fits comfortably. Re-derivation is
  possible in principle but budget-prohibitive.
- **Premise dispersion:** required premises are scattered across enough sessions and lexical
  frames that top-k retrieval cannot reassemble them, while the derived artifact is a single
  retrievable unit.

In addition, **reuse is measured from decision-time retrieval traces**, not inferred from answer
accuracy: a trial counts as reuse-dependent success only when the derived artifact (not its raw
ancestors) appears in the decision-time context. Raw success and reuse-dependent success are
reported separately.

### 10.2 Failure amplification

The benchmark should explicitly test the failure-amplification risk of storing derived
conclusions. Intermediate cognition can save recomputation, but incorrect intermediate cognition
can recursively pollute later decisions.

Primary recursive outputs are an accuracy-by-depth curve and a revision-by-depth curve, not only
an aggregate mean. Power analysis must cover each depth-tier curve point, not just the overall
comparison (Section 18).

## 11. Bitemporality and time travel

Every temporal scenario must distinguish:

- **Valid time:** when a fact, rule, state, or relationship applies in the world.
- **Transaction time:** when the agent learned, stored, revised, or stopped believing it.

The core query is conceptually:

```text
belief(valid_time=V, known_at=K)
```

### 11.1 Required temporal phenomena

- Late-arriving evidence.
- Retroactive corrections.
- Explicit and implicit retractions.
- Future-effective facts, policies, preferences, and intentions.
- Overlapping or scoped validity intervals.
- Reports whose publication time differs from event time.
- Erroneous records corrected without historical erasure.
- Decisions that were rational then but are unsupported now.
- Decisions that succeeded despite unsound reasoning.
- Decisions that failed despite sound reasoning under uncertainty.

### 11.2 Required time-travel probes

1. Reconstruct the world believed valid at `V` using information known by `K`.
2. Reconstruct the agent's actual knowledge state at transaction time `K`.
3. Judge whether an earlier decision was rational given only contemporaneous information.
4. Re-evaluate the decision using information known now.
5. Identify downstream artifacts requiring review after a retroactive correction.
6. Branch from a historical snapshot, introduce counterfactual evidence, and avoid contaminating
   the main timeline.

Snapshot querying should be a core outcome capability. Mutable branching may begin as an advanced
track if adapter burden would otherwise prevent broad system participation.

### 11.3 Clock discipline (approved 2026-07-16)

Transaction time is meaningless unless the harness controls the substrate's notion of *now*. Real
memory systems stamp writes with wall clock, and a benchmark run compresses months of scenario
time into minutes. The current harness has no time concept at all (`Event` carries no timestamp),
so this is a foundational schema and contract change.

Proposed semantics:

- The harness maintains a **virtual scenario clock** — monotonic logical time attached to every
  event and every adapter call (`logical_time` in Section 8).
- **Native mode:** the adapter persists logical timestamps as its transaction time. Bitemporal
  probes are scored at timestamp granularity. Zep/Graphiti-class systems that accept explicit
  timestamps qualify.
- **Mapped mode:** the substrate only wall-clock-stamps. The harness executes in strict scenario
  order, records the wall-to-scenario mapping, and scores transaction-time probes at **session
  granularity** rather than timestamp granularity.
- **None:** systems that can neither accept nor expose time report bitemporal probes as
  capability-absent (Section 6.3).
- No scenario may depend on real elapsed wall time (e.g., time-based decay); systems with
  wall-clock decay behavior document it as a limitation in their capability manifest.
- Published results are stratified by clock mode; native vs. mapped systems are never pooled on
  timestamp-granularity metrics.

These semantics freeze at Gate 1 with the rest of the adapter contract: the choice is
load-bearing for the flagship capability being iterated on, and a wrong clock makes the
bitemporal steering signal noise.

## 12. Auditability and causal lineage

The canonical lineage is:

```text
source -> observation -> evidence -> claim -> decision -> action -> outcome
```

### 12.1 Operational definition of faithfulness (new in v2)

Every audit receipt is generated retrospectively; what makes it *faithful* is agreement with the
**harness-logged decision-time trace** — the retrievals, injected context, and tool results the
agent actually had when it decided. Audit scoring therefore compares the receipt against the
logged decision-time context, never against narrative plausibility. A fluent rationale citing
evidence that was not in the decision-time context scores as leakage, however plausible.

For evaluator validation, the controlled generator mechanically mints **matched pairs of faithful
and contaminated rationales** (leaking one post-decision fact into an otherwise correct
rationale). The audit evaluator must meet a preregistered discrimination threshold on these pairs
at Gate 3.

### 12.2 Audit measurements

- Evidence coverage.
- Lineage precision and recall.
- Source attribution.
- Temporal provenance completeness.
- Claim-to-decision linkage.
- Decision-to-action and action-to-outcome linkage.
- Minimal sufficient support-set recovery.
- Explicit uncertainty and unsupported-assumption disclosure.
- Post-decision evidence leakage into historical rationales.
- Detection of invalidated dependencies.
- Counterfactual sensitivity to removal or alteration of cited evidence.
- Replayability of the decision context.

## 13. Task families

Resolved 2026-07-16: the first-release core is **three families**; three further families are
**tracks** built after the core validates, and the human-authored realism suite is deferred.

### 13.1 Core: recursive investigation

Incident response, diagnosis, or scientific investigation with competing hypotheses, requested
evidence, negative evidence, causal refinement, actions, and later corrections. This family runs
inside the executable environment (Section 14).

### 13.2 Core: bitemporal belief revision

Facts, reports, policies, or requirements with different event, effective, reporting, discovery,
and correction times. The primary carrier of RQ3 and RQ4.

### 13.3 Core: decision lineage

Consequential choices under incomplete information, followed by outcome observation and a later
audit of evidence, assumptions, alternatives, and decision-time rationality. The primary carrier
of RQ5.

### 13.4 Tracks (post-core)

- **Project cognition:** objectives, constraints, requirements, decisions, dependencies,
  completed work, failed executions, changed requirements, resumption, and avoidance of duplicate
  or invalid work. (Closest to the current MVP's `project_continuation`; its concepts are reused
  in deeper, bitemporal form.)
- **Counterfactual branching:** reconstruction of a prior state followed by alternate evidence or
  constraints, comparison of actual and counterfactual decision paths, and verification of
  snapshot isolation.
- **Rule and lesson induction:** multiple episodes support a scoped lesson or policy; later cases
  test consolidation, applicability, exception handling, overgeneralization, counterexamples, and
  revision.

### 13.5 Deferred: human-authored realism suite

After the controlled core is validated, a smaller human-authored suite spanning personal
preference evolution, prospective intentions, research synthesis, operational incident response,
project decision history, and compliance with retroactive rules. Resolved 2026-07-16: deferred
and **contingent** — built only if post-launch critique or adoption signals demand naturalistic
validity, with the go/no-go taken at the first post-launch review. No effort is reserved for it
before then.

## 14. Executable environment and decision semantics

Resolved 2026-07-16: the first release builds **one** deterministic executable environment — the
**service-incident simulator** — which gives the recursive-investigation and decision-lineage
families consequences beyond returning a JSON answer. All other families use structured-answer
tasks with deterministic scorers in v1. Additional environments (project-dependency simulator,
policy-effective-date simulator, resource allocation) are track material.

The simulator: a seeded world of services, dependencies, alerts, probes, and remediations with a
hidden root cause; agent actions have costs and alter future state; deterministic ground truth,
full replay, counterfactual evaluation, and an execution-based scorer.

The evaluator must distinguish:

- **Outcome:** whether the action worked.
- **Correctness:** whether it was optimal under the true world state.
- **Rationality:** whether it was justified by information available then.
- **Auditability:** whether that contemporaneous basis can be faithfully reconstructed.

This prevents lucky actions from receiving the same profile as sound decisions and prevents sound
decisions under uncertainty from being treated as wholly wrong because of unlucky outcomes.

## 15. Dataset construction

Use a hybrid construction methodology.

### 15.1 Controlled causal-world generator

Generate a hidden event, epistemic, derivation, decision, and outcome graph first. Render public
events only after the ground truth is fixed. The generator should support controlled
interventions on depth, temporal structure, contradiction, distractors, dependency invalidation,
and re-derivability (Section 10.1).

### 15.2 Natural-language realization

Use multiple independently authored realization patterns per causal structure. Lexicalization
should vary discourse order, indirectness, entity descriptions, source language, and cue wording
without changing the hidden world.

Do not count renamed entities or seeded lexical substitutions as independent structural
scenarios. If realizations are LLM-authored, disclose it, use a lexicalizer model disjoint from
the tested models, and human-rewrite a sampled fraction as a naturalness control.

### 15.3 Adversarial validation

Reviewers should try to solve scenarios without memory, exploit templates, identify ambiguous
answers, find unintended lexical shortcuts, and challenge causal and temporal annotations.

### 15.4 Canary and contamination

Every published dataset file carries a canary GUID. Published worlds ship with n-gram overlap
checks. The durable defense is regeneration: published claims always run on freshly minted worlds
(Section 2.4).

### 15.5 Splits

Create distinct splits for:

- Generator and evaluator unit tests.
- Development and prompt tuning (the iteration track's worlds).
- Calibration and power analysis.
- Frozen publication validation (freshly generated at freeze).
- Private or delayed-release challenge evaluation, if operationally feasible.

Publication holdout separates causal structures, domain realizations, and lexicalizers — not
merely random seeds.

### 15.6 Scale targets and budget

Resolved 2026-07-16: the frozen publication study is designed to a **≈ $50k model-spend
envelope** ("no compromises" within the three-family core), with the iteration run at
≤ ~$2,500 and a public lite tier at ≤ ~$200 (Section 16.4). A **run-cost model** — measured
per-world lifecycle cost extrapolated to the full matrix — is a Phase A deliverable and a
checked input at Gates 1, 4, and 6. Budget generosity buys worlds, models, repetitions, and
ablation coverage; it does not reopen family scope.

Provisional targets, finalized only by power analysis after the frozen pilot:

- Controlled core: 400–600 structurally distinct worlds across the three families and difficulty
  tiers, with enough worlds per depth tier to power each curve point.
- Environment family: 100+ distinct seeded incident worlds.
- Track families: 50–100 worlds each, run as exploratory until promoted.
- Multiple decision, audit, temporal, and reuse checkpoints per world.

The scenario/world remains the statistical unit; multiple checkpoints do not create independent
samples.

## 16. Conditions and baselines

The minimum comparison set should include:

- Stateless.
- Full transcript with an effectively unlimited context budget.
- Transcript under a matched read-token budget.
- Rolling or hierarchical summary.
- Flat BM25 retrieval.
- Vector retrieval.
- Hybrid lexical/vector retrieval.
- **Named external memory systems** (resolved 2026-07-16): **Mem0** (vector-notes/extraction
  family), **Zep/Graphiti** (temporal knowledge-graph family — the sharpest comparison for the
  bitemporal claims), and **Cognee** (graph-RAG family — a second graph system, testing whether
  any MindGraph edge comes from the graph representation or from the cognitive lifecycle).
  Letta/MemGPT (memory-OS family) is deferred as a later candidate adapter.
- CogMemBench's target structured system (MindGraph), treated identically to external systems.
- Oracle capture for every compatible substrate.
- Oracle cognitive ledger and evaluator gold answers.

Where systems expose active tools, compare passive prefetch and active-pull policies per the
matrix-restraint rule (Section 7.4). Predetermined retrieval remains available to separate
storage/retrieval quality from model tool policy.

### 16.1 Budget fairness

Report both:

1. Natural operating mode for each system, with complete lifecycle accounting.
2. Matched read-context and, where practical, matched total-cost comparisons.

The unlimited transcript is a truth-access ceiling, not the only deployment baseline.

### 16.2 Required ablations

- No provenance links.
- No temporal metadata.
- No evidence/claim distinction.
- No stored intermediate conclusions.
- No dependency tracking.
- No supersession.
- No active retrieval.
- No lesson consolidation.
- No audit receipt.

Ablations answer which substrate features improve outcomes, revision, and auditability — not only
whether a complete product wins. On the iteration track, each ablation delta is a direct roadmap
signal for MindGraph feature investment; this is the benchmark's highest-value product output.

### 16.3 Vendor review window

Before publication runs, each external system's adapter configuration and capability manifest is
shared with its maintainers with a fixed response window (e.g., two weeks). Responses, silence,
and any resulting configuration changes are recorded in the repository. Published results state
per system whether the configuration was vendor-reviewed.

### 16.4 Lite tier

Resolved 2026-07-16: a fixed, published configuration external researchers can run for ≤ ~$200:
one pinned model (the exact model chosen at Phase F against current pricing), ~60 worlds (~20 per
core family), five conditions (stateless, budget-matched transcript, BM25, hybrid,
system-under-test), one repetition. It must reproduce the headline depth and revision curves in
miniature. Low-friction adoption — `pip install`, an adapter kit,
and an affordable entry point — is a launch requirement, not an afterthought.

## 17. Metrics

Category scores are primary. Any composite must be secondary, fixed before publication runs, and
must not silently change its meaning when a condition lacks a metric. The **primary endpoints are
the RQ-designated metrics in Section 4**; everything else below is exploratory or diagnostic, and
Gate 3's full validation burden applies to primaries first.

### 17.1 Task and decision metrics

- Execution success.
- Task progress.
- Decision correctness.
- Decision-time rationality.
- Outcome quality.
- Constraint satisfaction.
- Duplicate or invalid action rate.

### 17.2 Recursive cognition metrics

- Accuracy by derivation depth (raw and reuse-dependent; Section 10.1).
- Intermediate-conclusion retention.
- Correct derived-artifact reuse (trace-verified).
- Unsupported inference rate.
- Reasoning contamination rate.
- Revision accuracy by dependency depth.
- Transfer and scope accuracy.
- Recomputation avoided and recomputation required.

### 17.3 Capture and retrieval metrics

- Durable artifact precision and recall.
- Artifact-type accuracy.
- Relation precision and recall.
- Non-durable contamination.
- Retrieval precision, recall, and ranking quality.
- Useful context per retrieved token.
- Stale and temporally inapplicable retrieval rate.

Instrumented-track artifact matching keeps strict one-to-one semantics (one broad summary cannot
satisfy several expected memories), but this strictness is diagnostic: outcome-track scoring must
accept alternative valid decompositions (Gate 3 granularity-equivalence tests), so a
coarse-but-effective system is penalized only on the instrumented profile, never on outcomes.

### 17.4 Revision metrics

- Stale conclusion intrusion.
- Dependency invalidation precision and recall.
- Downstream repair accuracy.
- Unaffected-artifact preservation.
- Supersession correctness.
- Appropriate uncertainty retention.

### 17.5 Bitemporal metrics

- Current-state accuracy.
- Valid-time accuracy.
- Known-at-time accuracy.
- Historical belief reconstruction.
- Decision-time context reconstruction.
- Late-arrival handling.
- Future-effective-state handling.
- Snapshot isolation.
- Branch contamination and restoration.

### 17.6 Audit metrics

- Evidence-to-claim lineage F1.
- Claim-to-decision lineage F1.
- Source attribution accuracy.
- Temporal provenance completeness.
- Minimal support-set accuracy.
- Post hoc evidence leakage.
- Replay reconstruction success.
- Counterfactual rationale fidelity.

### 17.7 Cognitive policy metrics

- Appropriate and missed writes.
- Harmful, speculative, and redundant writes.
- Appropriate, missed, and unnecessary retrievals.
- Correct revision operation.
- Premature or unjustified consolidation.
- Correct primitive selection where primitives exist.

### 17.8 Calibration and abstention (new in v2)

- Abstention appropriateness: abstaining when the substrate genuinely lacks the answer scores
  better than confabulating, and worse than answering when the evidence is present.
- Confidence calibration on claims and decisions (e.g., Brier score / expected calibration
  error), evaluated separately from correctness.
- Hedging audit: evaluators must not penalize honest, well-scoped uncertainty — a failure mode
  already observed in prior judge-based work — validated with matched hedged/confident gold
  pairs at Gate 3.

### 17.9 Efficiency metrics

- Total lifecycle tokens and cost.
- Memory-construction tokens and cost.
- Retrieval and read-context tokens.
- Model and embedding calls (including substrate-internal usage per Section 8, or explicit
  unavailability).
- Latency by lifecycle phase.
- Storage and index growth.
- Cost per successful task.
- Cost per correct recursive step.
- Cost per correct audit.
- Reuse savings relative to recomputation.

Missing provider measurements must remain missing, not zero.

## 18. Experimental design and statistics

### 18.1 Factorial design

The intended design crosses:

- Reasoning model.
- Memory substrate.
- Capture mode (restrained per Section 7.4).
- Retrieval policy (restrained per Section 7.4).
- Task family.
- Difficulty/depth tier.
- Repetition.

Use at least three materially different reasoning-model classes. Model diversity is
iteration-critical, not paper polish: observed smoke runs showed tool policy dominating outcomes
(one model never invoked retrieval), so steering MindGraph against a single model's tool-calling
style would overfit the product.

**Model pinning:** publication runs use natively snapshot-pinned models (provider-native APIs)
wherever available; router aliases without snapshot identifiers (the current OpenRouter
limitation) are acceptable on the iteration track only, and are always recorded.

### 18.2 Statistical unit and dependence

The world/scenario is the primary unit. Sessions, checkpoints, and questions within a world are
repeated measures. Seeded renderings of the same causal structure must not be treated as wholly
independent evidence.

**Repetition covers the full lifecycle.** Memory substrates are themselves stochastic (LLM-based
extraction, embedding nondeterminism), so a repetition means a fresh namespace and complete
re-ingestion — never re-asking questions against a previously built store.

### 18.3 Analysis

- Paired condition differences within world, model, and repetition.
- Hierarchical bootstrap that resamples worlds before within-world observations.
- Mixed-effects models, sketched now so power analysis has a target: treatment, model, and depth
  tier (and treatment × depth, treatment × model interactions) as fixed effects; random
  intercepts for world nested in structural template nested in family; hierarchical bootstrap as
  the nonparametric check.
- Family and structural-template variance.
- Effect sizes and uncertainty intervals, not only significance tests.
- Primary endpoints fixed in advance (Section 4) with proportionate multiplicity handling;
  journal-grade machinery beyond that is not required by the publication posture.
- Failure, timeout, and missingness analysis by condition.
- Sensitivity analyses excluding ambiguous or infrastructure-affected cases.

Perform power analysis after a frozen pilot and before fixing publication sample sizes; power
each depth-tier curve point for RQ2/RQ4, not only aggregate contrasts.

## 19. Validity and fairness controls

- Byte-identical public event streams across matched conditions.
- Hidden world, derivation, temporal, and scoring fields inaccessible to agents and substrates.
- Fresh namespace and verified reset per trial, with quiesce barriers (Section 8).
- Balanced condition order.
- Fixed prompts, tools, budgets, and model configuration within a comparison.
- The fixed reasoning scaffold (prompt, tool loop, step budget, retry policy) is a versioned,
  published artifact; scaffold sensitivity is acknowledged as a validity threat and checked with
  a two-scaffold robustness probe on a subsample.
- Exact preservation of model requests, responses, retrievals, writes, revisions, and environment
  actions.
- Model and substrate version hashes.
- No evaluator tuning on publication outputs.
- Human audit conducted blind to condition and product identity (targeted spot-audits of
  evaluator validity; not journal-scale full-condition audits).
- Explicit disclosure of benchmark-development changes prompted by pilot failures (the iteration
  log, Section 2.4).
- Equal opportunity for non-graph systems to provide provenance through IDs, metadata, or
  receipts.
- No task-success reward for using benchmark ontology vocabulary.

## 20. Governance, disclosure, and credibility

New in v2. The benchmark's core dimensions (bitemporality, provenance, supersession) are exactly
where the author's product differentiates, and the product is iterated against the benchmark.
Without structural mitigation this reads as marketing; with it, it can read as a methods
contribution.

- **Affiliation disclosure.** The MindGraph affiliation is stated in the repository README, the
  paper, and every published results table.
- **Everything runs in the open.** Generator, evaluators, harness, adapters, and analysis code
  are published under Apache-2.0; scenarios and datasets under CC BY 4.0 (resolved 2026-07-16 —
  the patent grant is scoped to the benchmark code only). Anyone can re-mint held-out worlds and
  reproduce any published number.
- **Fresh-world publication rule** (Section 2.4) — the structural answer to "you tuned your
  product on your own benchmark."
- **Vendor review window** for external-system configurations (Section 16.3).
- **No self-hosted leaderboard.** Consistent with our standing claim policy: publish a
  reproducible harness and results tables; never a self-anointed leaderboard. Third parties are
  free to host one.
- **Preregistration mechanics:** primary RQs, endpoints, and the frozen protocol are registered
  as a time-stamped repository hash (optionally mirrored to OSF); lightweight but tamper-evident.
- **External replication invited** at launch, with the lite tier as the on-ramp.
- **Solo authorship with named external reviewers** (resolved 2026-07-16). Authorship stays
  solo; two to three named external researchers adversarially review the protocol before Gate 7,
  and their critiques plus the responses are published in the repository. Upgradeable to
  co-authorship if a strong fit emerges from the outreach network.

## 21. Validation gates

Implementation and publication advance only through explicit gates. v2 distinguishes **hard
gates** (block everything downstream; full rigor always) from **publication-discipline gates**
(apply only to publication-track runs; the iteration track is exempt but confined to
non-publication worlds).

Because the benchmark steers the product, Gates 2–4 are the highest-stakes items in this plan: a
miscalibrated evaluator does not merely weaken a paper — it points the MindGraph roadmap at the
wrong problems.

### Gate 0 (hard): Identity and scope approval

- Benchmark identity, non-goals, research questions, and claims approved.
- Literature comparison (verified per Section 3) supports a distinct contribution.

### Gate 1 (hard): Formal specification freeze

- Artifact, relation, temporal, adapter, condition, and trace contracts frozen — including clock
  discipline (Section 11.3) and the quiesce/usage-reporting requirements (Section 8).
- Primary metrics (per RQ) and statistical unit defined.
- Run-cost model exists (Section 15.6).
- No product-specific fields in the canonical evaluator contract.

### Gate 2 (hard): Generator validity

- Hidden causal and temporal ledgers are internally consistent.
- Counterfactual and snapshot answers are mechanically derivable.
- Structural diversity tests prevent template-count inflation.
- Re-derivability controls verified (budget asymmetry and dispersion measurably present).

### Gate 3 (hard): Evaluator validity

- Gold answers score perfectly.
- Independent human annotations meet a preregistered agreement threshold (including the relation
  vocabulary decision rules, Section 5.3).
- Paraphrase, alternative-valid-action, and granularity-equivalence tests pass (Section 17.3).
- Incorrect, stale, temporally leaked, and post hoc rationales are rejected — validated against
  mechanically generated faithful/contaminated rationale pairs with a preregistered
  discrimination threshold (Section 12.1).
- Hedging audit passes (Section 17.8).

### Gate 4 (hard): Difficulty calibration

- Stateless baselines establish a meaningful floor.
- Full-information and oracle conditions establish interpretable ceilings.
- Flat or transcript baselines do not saturate all primary tasks, **and no non-oracle condition
  (including the target system) saturates them either** — a benchmark the flagship aces is as
  useless for iteration as one the transcript aces.
- Retrieval `k` is small relative to corpus size on retrieval-sensitive tiers.
- Difficulty increases monotonically enough to support depth analysis.
- Measured per-world costs project the publication matrix within the budget envelope.

### Gate 5 (hard): Adapter portability

- At least one flat, one vector/hybrid, and two independent external memory systems complete the
  same protocol (walking-skeleton evidence from Phase B counts toward contract validation, but
  the gate requires the full protocol).
- Unsupported capabilities are reported consistently; declared vs. observed capability audited
  (Section 6.3).
- Reset, quiesce, isolation, and accounting audits pass.

### Gates 6–8 (publication discipline): Pilot, freeze, execution

Compressed relative to v1; they bind only runs intended for publication.

- **Gate 6 — frozen pilot:** pilot on non-publication scenarios; failure analysis confirms
  metrics localize errors; power analysis and the publication matrix fixed within budget; any
  prompt or evaluator change happens here, and is logged.
- **Gate 7 — publication freeze:** freshly generated held-out scenarios; evaluators, prompts,
  conditions, models, analysis, and exclusion rules frozen; protocol hashes and repository state
  recorded (the preregistration artifact).
- **Gate 8 — publication execution:** runs complete without post hoc protocol changes;
  infrastructure failures and retries remain append-only and auditable; audits and analysis
  follow the frozen protocol.

## 22. Phased delivery plan

Re-sequenced in v2 around two principles: an end-to-end **walking skeleton** validates the
adapter contract against real external systems before generators and evaluators are built on it,
and the benchmark starts steering MindGraph at the earliest possible date rather than after the
full suite exists.

### Phase A: Research specification

Deliverables:

- Verified literature matrix and novelty statement (Section 3).
- Formal definition of cognitive substrate evaluation.
- Research questions with designated primary endpoints.
- Artifact, relation, and bitemporal specifications, including clock discipline.
- Outcome and instrumented-track contracts; adapter contract v2.
- Run-cost model (first version, from current-harness measurements).
- External protocol-reviewer shortlist (Section 20).

Exit: Gates 0 and 1 pass.

### Phase B: Harness v2 and walking skeleton

Deliverables:

- Representation-neutral substrate adapter v2 (logical time, quiesce, dual-axis snapshot,
  usage reporting, capability manifest).
- Event-sourced scenario and world-state schema with logical timestamps.
- Cognitive artifact and audit-receipt schema.
- Capture modes and condition contracts.
- **Walking skeleton:** one hand-built multi-phase scenario executed end-to-end — capture through
  audit receipt — against MindGraph, Mem0, and Zep/Graphiti, plus flat and transcript baselines.
- Backward-compatible import or archival path for current MVP artifacts.

Exit: skeleton runs on three real substrates; generic contract tests pass; existing MVP tests
remain valid or are intentionally versioned.

### Phase C: First vertical slice — bitemporal belief revision

Deliverables:

- Bitemporal event generator and revision/dependency propagation oracle for one family.
- Family evaluators for RQ3/RQ4 primary endpoints.
- Development-scale run: MindGraph + transcript + one external system.

Exit: **first steering milestone** — the benchmark produces its first trustworthy
product-steering report (Section 2.2). Iteration-track cadence begins here and continues through
all later phases.

### Phase D: Remaining core generators and environment

Deliverables:

- Derivation-DAG generator with re-derivability controls.
- Service-incident simulator (deterministic, replayable, counterfactual-capable).
- Counterfactual and snapshot oracle.
- Structural-diversity and leakage tests.

Exit: Gate 2 passes.

### Phase E: Evaluators and metrics

Deliverables:

- Execution, rationality, recursive, temporal, revision, audit, policy, calibration, and
  efficiency evaluators (primaries first).
- Depth and repair curves.
- Hierarchical aggregation and uncertainty analysis.
- Evaluator adversarial test corpus, including faithful/contaminated rationale pairs and
  granularity-equivalence cases.

Exit: Gate 3 passes. (Phases C–E interleave per family; each family lands generator + evaluator
together and joins the iteration cadence immediately.)

### Phase F: Core suites, baselines, and external adapters

Deliverables:

- Three core task families at target scale with difficulty tiers and multiple independent
  realization patterns.
- Transcript, summary, BM25, vector, hybrid, and oracle baselines.
- External adapters: Mem0, Zep/Graphiti, and Cognee.
- Natural-mode and matched-budget configurations; capability and cost-accounting manifests.
- Lite tier configuration (Section 16.4).

Exit: Gates 4 and 5 pass.

### Phase G: Pilot and protocol freeze

Deliverables:

- Multi-model pilot results.
- Human spot-audit and evaluator agreement report.
- Failure taxonomy.
- Power analysis; publication matrix fixed within budget.
- Vendor review window executed (Section 16.3).
- Frozen, hash-registered publication protocol.

Exit: Gates 6 and 7 pass.

### Phase H: Publication study and launch

Deliverables:

- Frozen held-out benchmark execution on freshly generated worlds.
- Complete raw traces and manifests.
- Primary, ablation, interaction, cost, and failure analyses.
- Reproducibility package + lite tier + adapter kit.
- arXiv paper, repository, and launch materials framed as the cross-system failure-mode map.

Exit: Gate 8 passes and all primary claims are traceable to frozen evidence.

## 23. Migration from the current benchmark

The current harness (~5k LOC, 50 tests) carries substantial machinery worth preserving. Phase B
executes against this disposition table rather than a rewrite-from-scratch:

| Current module | Disposition |
| --- | --- |
| `scenarios/schema.py` | **Extend.** `Event` gains logical timestamps (event time, report time); scenarios reference a hidden world ledger; schema version 2. Note: today `Event` has no time field at all — this is the deepest schema change. |
| `scenarios/generators/mvp.py`, `development_v2.py` | **Freeze** as the MVP compatibility suite; not primary evidence for recursive cognition or long-horizon capacity. |
| `agents/base.py`, `agents/development_v2.py` | **Refactor** into a phase-driven lifecycle executor (Section 9 phases). |
| `agents/oracle.py` | **Generalize** into oracle capture against any adapter (currently MindGraph-shaped). |
| `agents/tools.py` | **Extend** into the standardized cognitive-operation set (Section 7.2). |
| `memory/reference.py` | **Extend** with bitemporal semantics — becomes the ledger-conformant reference backend for CI. |
| `memory/flat_store.py` | **Keep**; add the metadata channel required for oracle capture. |
| `memory/mindgraph_client.py`, `mcp_stdio.py` | **Extend** to adapter v2 (dual-axis snapshot, quiesce, usage report). |
| `memory/reset.py` | **Keep**; extend contamination probes per new backend and quiesce semantics. |
| `evaluators/*` | **Keep** the deterministic core and canonicalization vocabulary; add the new evaluator families. |
| `runners/run.py`, `runners/locks.py`, `protocol.py` | **Keep.** Protocol locks, manifests, balanced scheduling, append-only resume, and repository-SHA stamping port essentially as-is and already implement Section 2.3's needs. |
| `telemetry/`, `reports/` | **Keep**; extend with depth/repair curves and the longitudinal regression table. |

Also preserved as protocol properties: public/evaluator data separation, paired treatment
execution, backend provenance labels, reset and contamination checks, observable traces without
hidden chain-of-thought, token/latency/storage/cost accounting, and deterministic CI providers.

Supersession in the current schema is point-in-time replacement (a `Supersedes` edge plus flag),
not queryable history; nothing bitemporal exists yet. The v1 four families are versioned as an
MVP compatibility/integration suite; their concepts (preference revision, project continuation,
failure learning) are reused inside deeper, executable, bitemporal scenarios rather than expanded
lexically. On adoption of this plan, reconcile `docs/TASKS.md` (which still references "ten
proposed publication families") and `docs/LIMITATIONS.md` with the Section 13 structure.

## 24. Paper framing and launch

A provisional paper framing is:

> **From Memory Store to Cognitive Substrate: Treatment-Controlled Evaluation of Recursive,
> Temporal, and Auditable Agent Memory**

Expected contributions:

1. A formal model of persistent cognitive artifacts and bitemporal lineage for agent evaluation.
2. A controlled benchmark where derived cognition is reused, revised, audited, and acted upon.
3. A representation-neutral protocol separating capture, retrieval, policy, reasoning use, and
   action.
4. Metrics for recursive decay, dependency repair, temporal reconstruction, and decision audit.
5. A multi-model, multi-substrate empirical study with causal ablations and complete lifecycle
   cost.

Publication posture (resolved 2026-07-16): **arXiv-first**, with code, data, lite tier, and
adapter kit released simultaneously; social and community distribution planned; formal venue
submission optional and never gating. The launch narrative is the cross-system failure-mode map
("here is where every current memory system, including ours, breaks"), not a product win. The
paper must remain valuable if the target structured system loses; negative results and
architecture-specific failure modes are first-class evidence.

## 25. Decisions

### Resolved 2026-07-16

1. **Purpose and posture:** decisive product-iteration instrument with co-primary researcher
   credibility; arXiv-first; peer review optional (Section 1.1).
2. **Core scope:** three core families — recursive investigation, bitemporal belief revision,
   decision lineage; project cognition, counterfactual branching, and rule/lesson induction are
   tracks (Section 13).
3. **Environments:** one executable environment in v1 — the service-incident simulator
   (Section 14).
4. **External adapter targets:** Mem0, Zep/Graphiti, and Cognee; Letta deferred as a later
   candidate (Section 16).
5. **Budget envelope:** ≈ $50k model spend for the frozen publication study; ≤ ~$2,500 per
   iteration run; ≤ ~$200 lite tier (Section 15.6).
6. **Clock discipline:** dual-mode virtual scenario clock as specified in Section 11.3 —
   native/mapped/none capability modes, session-granularity scoring for mapped systems,
   stratified reporting, never pooled across modes.
7. **License:** Apache-2.0 for code; CC BY 4.0 for scenarios and datasets (Section 20).
8. **Authorship:** solo, with two to three named external researchers adversarially reviewing
   the protocol before Gate 7 and their critiques published; upgradeable to co-authorship
   (Section 20).
9. **Lite tier:** one pinned model (chosen at Phase F), ~60 worlds (~20 per core family), five
   conditions, one repetition, ≤ ~$200 (Section 16.4).
10. **Realism suite:** contingent — go/no-go at the first post-launch review, driven by whether
    critique or adoption demands naturalistic validity (Section 13.5).

### Carried from v1 (recommended; formally approved with Gate 0)

11. Keep the CogMemBench name with "Cognitive Substrate Evaluation" as the subtitle.
12. Make snapshot/as-of queries core and mutable counterfactual branches an advanced track.
13. Require outcome-track compatibility from all systems; require audit export only for the
    instrumented track.
14. Use the hybrid controlled-generator methodology (realism suite contingent per Section 13.5).
15. Treat the scenario/world, not the checkpoint, as the statistical unit.
16. Keep category profiles and depth curves primary; no headline composite.
17. Require at least three independent external memory systems before making benchmark-wide
    claims.
18. Freeze prompts and evaluators only after a non-publication pilot and validation.
19. Publish the benchmark independently of any claim that a particular product wins.

## 26. Authorization boundary

The original plan document did not itself authorize implementation, paid model runs, or
publication. Credential-free implementation was subsequently authorized through separately scoped
implementation tranches and is now complete. Paid/live execution, formal gate declarations,
preregistration, and publication submission still require their explicit gate evidence and owner
authorization. All Section 25 open decisions were resolved on 2026-07-16; the carried v1 defaults
(items 11–19) are approved only when Gate 0 is formally signed off.
