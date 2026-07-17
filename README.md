# CogMemBench

**Treatment-controlled evaluation of persistent memory as a cognitive substrate for AI agents**

[![CI](https://github.com/shuruheel/cogmembench/actions/workflows/ci.yml/badge.svg)](https://github.com/shuruheel/cogmembench/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Code: Apache-2.0](https://img.shields.io/badge/code-Apache--2.0-green.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-green.svg)](DATA_LICENSE.md)

CogMemBench evaluates whether persistent memory helps an agent **preserve, reuse, revise,
reconstruct, and audit cognitive state over time**—not merely recall past text. It uses controlled
causal worlds to measure recursive reasoning, bitemporal belief revision, dependency repair,
decision provenance, and downstream action under matched memory treatments.

The benchmark is representation-neutral. A tested system may use documents, vectors, relational
tables, graphs, event logs, neural state, or a hybrid. CogMemBench scores what the agent can do with
the substrate and, where instrumentation is available, how faithfully the substrate preserved and
exposed the relevant cognition.

> **Current status:** the credential-free Cognitive Substrate 2.0 implementation is complete.
> Deterministic and reference runs validate benchmark machinery; they are not evidence that a
> model or memory system is effective. Live external-system runs, representative multi-model
> calibration, independent annotation, vendor review, and publication execution remain explicit
> scientific gates. See the [implementation status](docs/COGNITIVE_SUBSTRATE_IMPLEMENTATION_STATUS.md).

## Why this benchmark exists

Most memory benchmarks ask whether an agent can retrieve something said earlier. CogMemBench asks
what happens after memory becomes part of a reasoning lifecycle:

```text
evidence -> belief -> decision -> action -> outcome -> lesson
              ^                                  |
              +--------- revision and reuse -----+
```

A useful cognitive substrate should preserve the relationships in that lifecycle, make earlier
conclusions available under a bounded context budget, repair downstream cognition when a premise
changes, and reconstruct what evidence was actually available when a decision was made.

This makes CogMemBench a **diagnostic causal protocol**, not a broad conversational QA dataset and
not a single-score leaderboard. Its central output is a failure-mode profile: where capture,
organization, retrieval, interpretation, reasoning, or action breaks.

## What is evaluated

The first-release core contains three procedurally generated task families:

| Task family | Capability under test | Representative measurement |
| --- | --- | --- |
| Recursive investigation | Reuse a conclusion derived across earlier episodes, then repair and reuse it after a required premise changes | Trace-verified accuracy and revision curves by derivation depth |
| Bitemporal belief revision | Distinguish when something was true from when it became known | Accuracy of `belief(valid_time=V, known_at=K)` and selective dependency repair |
| Decision lineage | Act under incomplete information and later reconstruct the contemporaneous basis for the decision | Decision-time context recovery, rationality, execution, and post-hoc leakage |

Recursive-investigation and decision-lineage worlds run in a deterministic service-incident
simulator, so decisions have costs and observable consequences. The hidden event, derivation,
temporal, and decision ledgers are fixed before their public natural-language realization is
rendered.

Measurements are reported by category rather than collapsed into one headline number:

- task execution and decision quality;
- recursive reuse, repair, contamination, and recomputation;
- valid-time and known-at-time reconstruction;
- dependency invalidation and unaffected-history preservation;
- evidence, decision, action, and outcome lineage;
- capture and retrieval policy quality;
- calibration, abstention, tokens, latency, storage, and cost.

## Experimental structure

Every compatible substrate is exercised through the same treatment contract. Public events,
reasoning scaffold, model, step budget, and read-context budget remain matched within a
comparison.

| Treatment | What it isolates |
| --- | --- |
| `stateless` | No cross-episode state |
| `transcript` | Transcript replay under the same read-token ceiling as retrieval treatments |
| `transcript-full` | Full-history truth-access ceiling |
| `automatic-passive` | The deployed system's end-to-end capture and retrieval behavior |
| `agent-directed-active` | A fixed agent using standardized write, relation, revision, and retrieval operations |
| `oracle-passive` | Correct canonical artifacts written at annotated transition points, isolating retrieval and use from capture |

Results are separated into two tracks:

- **Outcome track:** black-box task, temporal, revision, audit, and efficiency outcomes. Every
  system can participate without exposing an internal ontology.
- **Instrumented substrate track:** artifact, relation, temporal, retrieval, and audit-receipt
  diagnostics for systems that can export them. Unsupported capabilities are reported as absent,
  never silently scored as zero.

Capture-mode deltas localize failure along this pipeline:

```text
capture -> organization -> retrieval -> interpretation -> reasoning -> action
```

## Design controls that matter

- **Re-derivation control.** At reuse checkpoints, raw premises exceed the read budget and are
  dispersed across episodes. Success counts as reuse-dependent only when the stored derived
  artifact appears in the decision-time trace.
- **Two independent clocks.** Events distinguish valid time from transaction time. Adapters
  declare native, mapped, or absent clock support, and incompatible clock granularities are not
  pooled.
- **Faithful audit, not plausible narrative.** Audit receipts are checked against context the
  harness logged at decision time. Later evidence presented as an earlier rationale is leakage.
- **World-level statistics.** The scenario is the statistical unit; its checkpoints are repeated
  observations, not independent samples.
- **Fresh-world publication rule.** Publication worlds must be generated after iteration and
  differ in causal structure, realization, and lexicalization—not just random seed.
- **No private chain of thought.** The benchmark records public events, explicit cognitive
  artifacts, retrievals, tool calls, actions, and outcomes only.

## Five-minute local run

The local reference path is credential-free and requires Python 3.10 or newer:

```bash
git clone https://github.com/shuruheel/cogmembench.git
cd cogmembench
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

cogmembench generate --scale smoke --seed 42 \
  --generator-version cognitive-v2 \
  --output scenarios/fixtures/cognitive-v2-smoke-42.jsonl

cogmembench validate-cognitive-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-smoke-42.jsonl

cogmembench run-cognitive-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-smoke-42.jsonl \
  --model deterministic-v1 --adapter reference --run-id local-smoke

cogmembench report-cognitive-v2 --run-id local-smoke
```

The deterministic provider tests scheduling, isolation, tracing, gold consistency, evaluation,
and reporting. It must not be cited as a model or substrate result. The generated steering report
is written to `results/aggregated/local-smoke-steering.md`.

For validation suites, ablations, local baselines, real models, external adapters, release
preparation, and MindGraph server setup, see the [running guide](docs/RUNNING.md) and
[reproducibility package](docs/REPRODUCIBILITY_V2.md).

## Supported adapters

The adapter contract covers logical time, quiescence, namespace isolation, dual-axis snapshots,
bounded retrieval, audit export, capability reporting, and explicit usage fidelity.

| Adapter | Role | Evidence mode |
| --- | --- | --- |
| `reference` | Deterministic ledger-conformant harness reference | Native |
| `flat` | Okapi BM25 baseline | Local canonical rendering |
| `summary` | Rolling extractive-summary baseline | Local canonical rendering |
| `vector` | Dense-retrieval baseline | Local canonical rendering |
| `hybrid` | BM25/vector reciprocal-rank fusion baseline | Local canonical rendering |
| `mindgraph-v2` | MindGraph public HTTP adapter | Mapped |
| `mem0-oss` | Self-hosted Mem0 REST adapter | Mapped |
| `zep-cloud` | Zep Cloud Graph API adapter | Mapped |
| `cognee` | Cognee REST API adapter | Mapped |

“Mapped” means the adapter persists a reversible canonical operation journal inside the tested
service and reconstructs scored state from records read back from that service. A harness-only
sidecar is inadmissible for substrate credit. Adapter presence is not evidence that its live
scientific validation gate has passed; the status document records that boundary.

See the [external adapter kit](docs/EXTERNAL_ADAPTER_KIT.md) to add or audit a substrate.

## Repository map

| Path | Purpose |
| --- | --- |
| `cogmembench/scenarios/` | Public/hidden schemas, causal-world generators, and release controls |
| `cogmembench/substrate/` | Representation-neutral contracts, treatments, and adapters |
| `cogmembench/environments/` | Deterministic executable environments |
| `cogmembench/evaluators/` | Outcome and instrumented-track scoring |
| `cogmembench/runners/` | Balanced execution, manifests, traces, and protocol locks |
| `cogmembench/analysis/` | Hierarchical, ablation, calibration, cost, power, and failure analysis |
| `configs/` | Profiles, model settings, completion evidence, and freeze specifications |
| `docs/` | Protocol, methodology, governance, limitations, and implementation evidence |
| `tests/` | Contract, generator, evaluator, runner, release, and analysis tests |

Start with the [protocol specification](docs/COGNITIVE_V2_PROTOCOL.md), then read the
[methodology](docs/METHODOLOGY.md) and [metrics](docs/METRICS.md). The original
[cognitive-substrate upgrade plan](docs/COGNITIVE_SUBSTRATE_UPGRADE_PLAN.md) explains the design
rationale and phased research program; the [completion ledger](docs/COGNITIVE_SUBSTRATE_COMPLETION_LEDGER.md)
maps that plan to implementation evidence.

The earlier four-family cross-session benchmark remains available as the schema-v1 compatibility
suite through `cogmembench generate`, `run`, `evaluate`, and `report`. It is maintained for
regression and integration coverage, not as primary Cognitive Substrate 2.0 evidence.

## MindGraph relationship and governance

CogMemBench is created and maintained by MindGraph's authors and is used as a longitudinal
instrument for improving MindGraph. That is a real conflict of interest, not a claim of
independence.

The benchmark addresses it structurally: all systems receive byte-identical public streams;
MindGraph uses the same public adapter contract; outcome scoring does not require graphs or reward
benchmark ontology vocabulary; publication claims require fresh structural holdouts, frozen
protocol hashes, independent human annotation, external protocol review, and a vendor review
window. Generator, harness, evaluators, adapters, and analyses are public. The intended launch
narrative is a cross-system failure map—including MindGraph's failures—not a product victory
claim.

No scientific gate passes merely because its code exists. The authoritative boundary is in the
[implementation status](docs/COGNITIVE_SUBSTRATE_IMPLEMENTATION_STATUS.md), with known threats in
[limitations](docs/LIMITATIONS.md) and fairness rules in [fairness](docs/FAIRNESS.md).

## Contributing and licensing

Issues, external adapters, adversarial scenarios, evaluator challenges, and independent
replications are welcome. Changes that affect benchmark meaning should include tests and an entry
in the append-only [iteration log](docs/ITERATION_LOG.md).

Benchmark software, generators, evaluators, configurations, and analysis code are licensed under
Apache-2.0. Generated scenarios and dataset artifacts are licensed under CC BY 4.0; see
[DATA_LICENSE.md](DATA_LICENSE.md).
