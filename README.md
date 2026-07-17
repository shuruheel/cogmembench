# CogMemBench

CogMemBench is a treatment-controlled benchmark for persistent cognitive memory in agents.
It compares stateless, transcript replay, flat BM25, MindGraph passive, and MindGraph active
prefetch conditions on multi-session preference, belief-revision, project-continuation and
failure-learning tasks. Optional `flat-hybrid` and `mindgraph-active-pull` ablations isolate
embedding quality and model-initiated retrieval policy.

The benchmark distinguishes `reference` smoke runs from actual `mindgraph-local` and
`mindgraph-cloud` evidence. Reference results validate the harness only.

The credential-free Cognitive Substrate 2.0 implementation is complete. The three core families
run through five
capture/retrieval treatments—stateless, budget-matched transcript, automatic capture/passive
retrieval, agent-directed capture/active retrieval, and oracle capture/passive retrieval—plus a
separate full-transcript ceiling. Runs emit separate outcome-track evaluations, explicit
capability coverage, and a steering report. The existing four-family benchmark remains available
as the schema-v1 compatibility suite.

MindGraph's authors maintain this benchmark and use it to steer MindGraph development. That
conflict is addressed through fresh structural holdouts, complete open artifacts, explicit
native/mapped evidence labels, independent annotation and review gates, and a failure-map launch
posture—not by treating the benchmark as an independent product endorsement. See the
[completion ledger](docs/COGNITIVE_SUBSTRATE_COMPLETION_LEDGER.md) for the exact boundary between
implemented machinery and unexecuted scientific gates.

## Install and reproduce

```bash
cd cogmembench
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

cogmembench inspect
cogmembench generate --scale smoke --seed 42
cogmembench run --scale smoke --model deterministic-v1 \
  --conditions stateless,transcript,flat,mindgraph-passive,mindgraph-active-prefetch
cogmembench evaluate --run-id latest
cogmembench report --run-id latest
cogmembench export-trajectories --run-id latest
```

Development harness run:

```bash
cogmembench generate --scale development --seed 42
cogmembench run --scale development --model deterministic-v1 --resume
cogmembench report --run-id latest
```

Cognitive-v2 generator and mechanical oracle-ceiling validation:

```bash
cogmembench generate --scale development --seed 42 \
  --generator-version cognitive-v2 --output scenarios/fixtures/cognitive-v2-42.jsonl
cogmembench validate-cognitive-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-42.jsonl \
  --output results/aggregated/cognitive-v2-42-validation.json
cogmembench validate-generators-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-42.jsonl \
  --output results/aggregated/cognitive-v2-42-generator-validity.json
cogmembench validate-evaluators-v2 \
  --output results/aggregated/cognitive-v2-evaluator-adversarial.json
cogmembench validate-counterfactuals-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-42.jsonl \
  --output results/aggregated/cognitive-v2-42-counterfactuals.json
cogmembench validate-adapter-v2 --adapter reference
cogmembench validate-adapter-v2 --adapter flat
cogmembench validate-adapter-v2 --adapter summary --portability-audit
cogmembench validate-adapter-v2 --adapter vector --portability-audit
cogmembench validate-adapter-v2 --adapter hybrid --portability-audit
```

Cognitive-v2 treatment run and longitudinal steering comparison:

```bash
cogmembench run-cognitive-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-42.jsonl \
  --model deterministic-v1 \
  --conditions stateless,transcript,transcript-full,automatic-passive,agent-directed-active,oracle-passive \
  --adapter reference \
  --run-id cognitive-v2-reference-$(date +%Y%m%d)

cogmembench report-cognitive-v2 \
  --run-id cognitive-v2-reference-$(date +%Y%m%d) \
  --previous-run-id cognitive-v2-reference-previous
```

`run-cognitive-v2` uses balanced condition order, a fresh substrate namespace per trial, logical
scenario time, bounded retrieval, observable tool traces, and separate raw/evaluated artifacts.
`transcript` uses the same read-token ceiling as retrieval treatments; `transcript-full` replays
the complete preceding stream. `--retrieval-k` and `--retrieval-tokens` are frozen in the run
manifest.
The deterministic provider is a CI harness probe, not evidence of model or substrate quality.
Real models use the same provider environment variables documented below.
The default reasoning scaffold is `canonical-v1`; the preregistered sensitivity subsample repeats
selected cells with `--scaffold minimal-v1`. Both prompt text and its SHA-256 are recorded in the
run manifest.

`validate-generators-v2` hashes lifecycle/ledger/DAG shapes independently from domain wording,
enforces causal-world uniqueness and template-concentration thresholds, and scans public events
for evaluator IDs or direct checkpoint answers. `validate-evaluators-v2` runs matched positive and
negative cases for bounded hedging, paraphrase, granularity equivalence, stale beliefs,
unsupported reuse, equivalent valid remediation wording, and post-hoc evidence. These are
mechanical controls; Gate 3 still requires independent human agreement.

Cognitive-v2 profiles are `smoke` (1 variant/family), `development` (5), `lite` (20),
`calibration` (40), and `publication` (150). Each seed/variant pair changes causal parameters,
not only scenario labels. Easy/medium/hard tiers control temporal distractors, derivation depth,
decision context, and incident topology. For example, a 120-scenario calibration suite is:

```bash
cogmembench generate --scale calibration --seed 42 \
  --generator-version cognitive-v2 --output scenarios/fixtures/cognitive-v2-calibration-42.jsonl
```

`validate-counterfactuals-v2` checks incident snapshots by forking correct-remediation,
wrong-remediation, and wrong-target branches, requiring divergent outcomes and verifying replay,
snapshot restoration, and branch isolation.
Runner manifests report stratum counts, evaluated rows retain safe difficulty controls, and
steering JSON includes per-family task success by difficulty tier and treatment condition.

Single-feature ablation runs use the same public scenario file and runner contract:

```bash
cogmembench run-cognitive-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-calibration-42.jsonl \
  --conditions stateless,automatic-passive \
  --adapter reference --run-id cognitive-v2-full

cogmembench run-cognitive-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-calibration-42.jsonl \
  --conditions stateless,automatic-passive \
  --adapter reference --ablation no-temporal-metadata \
  --run-id cognitive-v2-no-temporal

cogmembench analyze-cognitive-v2 \
  --evaluated results/evaluated/cognitive-v2-full.jsonl,results/evaluated/cognitive-v2-no-temporal.jsonl \
  --output results/aggregated/cognitive-v2-ablation-analysis.json

cogmembench failures-cognitive-v2 \
  --evaluated results/evaluated/cognitive-v2-full.jsonl
cogmembench cost-cognitive-v2 \
  --evaluated results/evaluated/cognitive-v2-full.jsonl --profile iteration
cogmembench power-cognitive-v2 \
  --evaluated results/evaluated/cognitive-v2-full.jsonl \
  --treatment automatic-passive --baseline transcript \
  --minimum-effect 0.10 --assumed-sd 0.30
```

The other supported removals are `no-provenance-links`,
`no-evidence-claim-distinction`, `no-stored-intermediate-conclusions`,
`no-dependency-tracking`, `no-supersession`, `no-active-retrieval`,
`no-lesson-consolidation`, and `no-audit-receipt`. Analysis treats scenarios as the primary unit,
pairs rows by scenario/model/repetition, rejects mismatched public hashes, and performs a nested
template/world/observation bootstrap. The mixed-effects model remains a frozen-pilot target rather
than a dependency of the lightweight CLI.

Recursive scenarios contain four evaluated checkpoints: initial derivation, budget-controlled
reuse, conclusion repair after a required premise is invalidated, and budget-controlled reuse of
the revised conclusion. Reports separate raw answer accuracy from trace-verified initial and
repaired reuse, stale-conclusion intrusion, failure-amplification avoidance, and execution against
the corrected incident world. `analyze-cognitive-v2` emits both accuracy-by-depth and
revision-by-depth curves.
The same analysis also reports confidence calibration and expected calibration error when
evaluated rows contain confidence observations.

Local cognitive-v2 baseline adapters are `flat` (Okapi BM25), `summary` (rolling extractive
summary), `vector`, and `hybrid` (BM25/vector reciprocal-rank fusion at `k=60`). BM25, vector, and
hybrid index the same canonical rendering; summary compresses the same temporally visible artifact
fields. A matched smoke matrix can run the same `automatic-passive` condition once per adapter:

```bash
for adapter in flat summary vector hybrid; do
  cogmembench run-cognitive-v2 \
    --scenarios scenarios/fixtures/cognitive-v2-42.jsonl \
    --conditions automatic-passive \
    --adapter "$adapter" \
    --run-id "cognitive-v2-${adapter}-$(date +%Y%m%d)"
done
```

With `deterministic-v1`, vector and hybrid use credential-free feature hashing solely to test the
harness. Real-model runs require `COGMEMBENCH_EMBEDDING_API_KEY` (or `OPENAI_API_KEY`), with
optional `COGMEMBENCH_EMBEDDING_BASE_URL` and `COGMEMBENCH_EMBEDDING_MODEL`. Embedding calls,
input usage, model identity, fusion legs, and scores are retained in usage reports and traces.

External adapter walking skeletons use an append-only canonical journal persisted inside the
tested service. This is reported as `evidence_mode=mapped`; no harness-only mirror is scored.
Run the portability audit directly when diagnosing an adapter:

```bash
# MindGraph public HTTP API
MINDGRAPH_BASE_URL=http://127.0.0.1:18790 \
  cogmembench validate-adapter-v2 --adapter mindgraph-v2 --portability-audit

# Self-hosted Mem0 OSS REST server
MEM0_BASE_URL=http://127.0.0.1:8000 MEM0_API_KEY=... \
  cogmembench validate-adapter-v2 --adapter mem0-oss --portability-audit

# Zep Cloud Graph API
ZEP_API_KEY=... \
  cogmembench validate-adapter-v2 --adapter zep-cloud --portability-audit

# Cognee REST API v1
COGNEE_BASE_URL=http://127.0.0.1:8000 COGNEE_API_KEY=... \
  cogmembench validate-adapter-v2 --adapter cognee --portability-audit
```

The same adapter names are accepted by `run-cognitive-v2`. Every non-reference treatment run
executes this portability audit as a mandatory preflight and stops before trials if it fails.
MindGraph reset
deletes only nodes owned by the trial's derived agent namespace; Mem0 deletes only the trial user
scope; Zep uses a dedicated graph per trial. External internal-model and embedding usage remains
an explicit lower bound until a service exposes complete accounting.

Use `--operating-mode matched-budget` for the fixed comparison budget. Use
`--operating-mode natural` only with separately frozen, vendor-reviewed adapter settings supplied
through `--retrieval-k` and `--retrieval-tokens`; the exact label and settings are retained in the
manifest.

Publication candidates are canaried and audited before an immutable freeze:

```bash
cogmembench prepare-cognitive-v2-release \
  --scenarios scenarios/held_out/newly-generated.jsonl --split publication \
  --reference development=scenarios/fixtures/cognitive-v2-calibration-42.jsonl \
  --output scenarios/held_out/publication-v2.jsonl

cogmembench freeze-cognitive-v2-protocol \
  --spec configs/cognitive_v2_freeze.example.json \
  --output configs/protocols/cognitive-v2-publication.json
```

The freeze verifies and hashes the adjacent release manifest and its passing structural
separation audit. Do not create the real publication freeze until the pilot, human agreement,
vendor review, and cost/power gates pass.

Real-model runs use OpenRouter's OpenAI-compatible API. The inexpensive pinned configuration
is `qwen/qwen3-32b` on DeepInfra with provider fallbacks disabled:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
cogmembench run --scale smoke --model qwen/qwen3-32b --backend reference
```

The cost-balanced stronger configuration is `strong-model`, currently
`openai/gpt-5.4-mini` pinned to OpenRouter's OpenAI provider with fallbacks disabled. The
tested-agent model can change between matched runs; the server extraction model must remain
fixed for the model/tool-policy ablation.

Actual local MindGraph additionally requires a running server. The command below enables
OpenAI embeddings while retaining OpenRouter for extraction. `OpenAIChatProvider` appends
`/v1/chat/completions`, so its OpenRouter base is `/api` (the Python benchmark provider uses
`/api/v1`). Automatic wiki compilation is disabled because it is outside the memory treatment,
adds unmetered LLM calls, and can outlive graph reset.

```bash
# Terminal 1, from the workspace root
cd mindgraph-rs
CARGO_TARGET_DIR=../mnestic/target cargo build -p mindgraph-server
set -a
source ../cogmembench/.env
set +a
MINDGRAPH_DB_PATH=:memory: \
MINDGRAPH_LLM_API_KEY="$OPENROUTER_API_KEY" \
MINDGRAPH_LLM_BASE_URL=https://openrouter.ai/api \
MINDGRAPH_LLM_MODEL=qwen/qwen3-32b \
MINDGRAPH_LLM_PROVIDER_ONLY=deepinfra \
MINDGRAPH_LLM_REASONING=off \
MINDGRAPH_LLM_MAX_OUTPUT_TOKENS=8192 \
MINDGRAPH_EMBEDDING_MODEL=text-embedding-3-small \
MINDGRAPH_WIKI_MAX_TOKENS=8192 \
MINDGRAPH_WIKI_AUTOCOMPILE=off \
MINDGRAPH_MAX_INGESTION_CHUNKS=1 \
../mnestic/target/debug/mindgraph-server

# Terminal 2
cd cogmembench
MINDGRAPH_BASE_URL=http://127.0.0.1:18790 \
cogmembench run --scale smoke --seed 42 --model qwen/qwen3-32b \
  --backend mindgraph-local \
  --conditions stateless,transcript,flat,flat-hybrid,mindgraph-passive,mindgraph-active-prefetch,mindgraph-active-pull \
  --run-id smoke-openrouter-local-$(date +%Y%m%d)
```

The runner defaults to a 180-second provider read timeout and a 300-second MindGraph job
timeout. Override them with `COGMEMBENCH_PROVIDER_TIMEOUT_SECONDS` and
`COGMEMBENCH_MINDGRAPH_TIMEOUT_SECONDS`. With `OPENAI_API_KEY`, the runner refuses a local
MindGraph run unless its startup diagnostic observes both `fts` and `vec` contributions and
verifies that reset removes vector and full-text state. `flat-hybrid` uses the same
`MINDGRAPH_EMBEDDING_MODEL` through OpenAI and reports embedding calls, tokens, latency, and
estimated cost separately.

Never compare or pool reference and actual-MindGraph runs. See `docs/METHODOLOGY.md`, the
[implementation status](docs/COGNITIVE_SUBSTRATE_IMPLEMENTATION_STATUS.md), and the
[completion ledger](docs/COGNITIVE_SUBSTRATE_COMPLETION_LEDGER.md).

## Artifacts

Runs write checkpointed JSONL to `results/raw`, traces to `results/traces`, aggregate JSON to
`results/aggregated`, trajectories to `results/trajectories`, and the current generated report to
`docs/RESULTS.md`. Each run includes prompt/config hashes and repository SHAs.

## Licensing

Benchmark software, generators, evaluators, configurations, and analysis code are Apache-2.0.
Generated scenarios and dataset artifacts are CC BY 4.0; see [DATA_LICENSE.md](DATA_LICENSE.md).
