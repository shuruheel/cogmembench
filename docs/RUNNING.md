# Running CogMemBench

This guide contains the operational detail intentionally kept out of the community-facing
README. It covers credential-free validation, cognitive-v2 experiments, ablations, adapters,
provider-backed models, and release preparation.

Deterministic reference results validate benchmark machinery only. Never present or pool them as
evidence about a real model or memory substrate.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cogmembench inspect
```

## Generate and validate cognitive-v2 worlds

```bash
cogmembench generate --scale development --seed 42 \
  --generator-version cognitive-v2 \
  --output scenarios/fixtures/cognitive-v2-42.jsonl

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
```

`validate-generators-v2` hashes lifecycle, ledger, and DAG shapes independently from wording;
enforces causal-world uniqueness and template-concentration thresholds; and scans public events
for evaluator IDs or direct checkpoint answers. `validate-evaluators-v2` exercises matched
positive and negative cases for hedging, paraphrase, granularity equivalence, stale beliefs,
unsupported reuse, alternative valid remediation wording, and post-hoc evidence. These are
mechanical controls; independent human agreement remains required for Gate 3.

Available profiles are `smoke` (1 variant per family), `development` (5), `lite` (20),
`calibration` (40), and `publication` (150). A calibration suite therefore contains 120 worlds:

```bash
cogmembench generate --scale calibration --seed 42 \
  --generator-version cognitive-v2 \
  --output scenarios/fixtures/cognitive-v2-calibration-42.jsonl
```

## Run and report a treatment matrix

```bash
cogmembench run-cognitive-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-42.jsonl \
  --model deterministic-v1 \
  --conditions stateless,transcript,transcript-full,automatic-passive,agent-directed-active,oracle-passive \
  --adapter reference --run-id cognitive-v2-reference

cogmembench report-cognitive-v2 --run-id cognitive-v2-reference
```

The runner uses balanced condition order, a fresh namespace per trial, logical scenario time,
bounded retrieval, observable tool traces, and separate raw and evaluated artifacts. `transcript`
uses the retrieval treatments' read-token ceiling; `transcript-full` replays the complete earlier
stream. `--retrieval-k`, `--retrieval-tokens`, the scaffold version, and the prompt hash are
recorded in the manifest.

The default reasoning scaffold is `canonical-v1`. The protocol's sensitivity subsample uses
`--scaffold minimal-v1` and is analyzed separately rather than pooled.

To compare an iteration against an earlier steering report:

```bash
cogmembench report-cognitive-v2 \
  --run-id cognitive-v2-current --previous-run-id cognitive-v2-previous
```

## Analyze ablations, cost, power, and failures

Run full and ablated cells against the same public scenario file:

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

Other supported removals are `no-provenance-links`, `no-evidence-claim-distinction`,
`no-stored-intermediate-conclusions`, `no-dependency-tracking`, `no-supersession`,
`no-active-retrieval`, `no-lesson-consolidation`, and `no-audit-receipt`.

Analysis treats worlds as the primary unit, pairs rows by scenario/model/repetition, rejects
mismatched public hashes, and performs a nested template/world/observation bootstrap. It emits
accuracy-by-depth and revision-by-depth curves, matched treatment and ablation deltas,
missingness, calibration, and the frozen mixed-effects target specification.

## Run local baseline adapters

First validate their contract and portability behavior:

```bash
cogmembench validate-adapter-v2 --adapter reference
cogmembench validate-adapter-v2 --adapter flat --portability-audit
cogmembench validate-adapter-v2 --adapter summary --portability-audit
cogmembench validate-adapter-v2 --adapter vector --portability-audit
cogmembench validate-adapter-v2 --adapter hybrid --portability-audit
```

Then run a matched matrix:

```bash
for adapter in flat summary vector hybrid; do
  cogmembench run-cognitive-v2 \
    --scenarios scenarios/fixtures/cognitive-v2-42.jsonl \
    --conditions automatic-passive --adapter "$adapter" \
    --run-id "cognitive-v2-${adapter}"
done
```

BM25, vector, and hybrid index the same canonical rendering; summary compresses the same
temporally visible fields. With `deterministic-v1`, vector and hybrid use credential-free feature
hashing to test the harness. Provider embeddings require `COGMEMBENCH_EMBEDDING_API_KEY` or
`OPENAI_API_KEY`; optional settings are `COGMEMBENCH_EMBEDDING_BASE_URL` and
`COGMEMBENCH_EMBEDDING_MODEL`.

## Validate and run external adapters

Every non-reference treatment run performs a mandatory portability preflight before scheduling
trials. Run it directly when diagnosing an integration:

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

The same adapter names are accepted by `run-cognitive-v2`. Use
`--operating-mode matched-budget` for fixed comparison budgets. Use
`--operating-mode natural` only with separately frozen, vendor-reviewed `--retrieval-k` and
`--retrieval-tokens` settings. Never pool natural and matched-budget results.

See [EXTERNAL_ADAPTER_KIT.md](EXTERNAL_ADAPTER_KIT.md) for mapping and evidence semantics.

## Use provider-backed reasoning models

Real-model runs use an OpenAI-compatible provider. With OpenRouter, set the credential and pass an
exact configured model identifier:

```bash
export OPENROUTER_API_KEY=...
cogmembench run-cognitive-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-42.jsonl \
  --model qwen/qwen3-32b --adapter reference --run-id provider-smoke
```

Model aliases and provider routing are configured in `configs/models.yaml`. Publication runs
require provider-native snapshot pinning wherever available; unpinned router aliases are
iteration evidence only.

## Run a local MindGraph integration

MindGraph must be started independently. The exact server command depends on the sibling
MindGraph checkout and is not part of this standalone repository. The benchmark-facing contract
requires a reachable public HTTP server:

```bash
MINDGRAPH_BASE_URL=http://127.0.0.1:18790 \
  cogmembench validate-adapter-v2 --adapter mindgraph-v2 --portability-audit

MINDGRAPH_BASE_URL=http://127.0.0.1:18790 \
  cogmembench run-cognitive-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-42.jsonl \
  --model deterministic-v1 --adapter mindgraph-v2 --run-id mindgraph-smoke
```

The adapter resets only nodes owned by the trial's derived namespace. Automatic wiki compilation
must be disabled for matched runs because it is outside the treatment, adds unmetered model calls,
and may outlive graph reset. External internal-model and embedding usage remains an explicit lower
bound unless the service exposes complete accounting.

## Prepare a publication candidate

Publication candidates are canaried, checked against named development references, and audited
before an immutable freeze:

```bash
cogmembench prepare-cognitive-v2-release \
  --scenarios scenarios/held_out/newly-generated.jsonl --split publication \
  --reference development=scenarios/fixtures/cognitive-v2-calibration-42.jsonl \
  --output scenarios/held_out/publication-v2.jsonl

cogmembench freeze-cognitive-v2-protocol \
  --spec configs/cognitive_v2_freeze.example.json \
  --output configs/protocols/cognitive-v2-publication.json
```

Do not create the real publication freeze until the pilot, independent human agreement, vendor
review, and cost/power gates pass. The checked-in example is scaffolding and must not be frozen
unchanged. See [REPRODUCIBILITY_V2.md](REPRODUCIBILITY_V2.md) for annotation and publication-bundle
requirements.

## Compatibility suite

The earlier schema-v1 integration suite remains available:

```bash
cogmembench generate --scale smoke --seed 42
cogmembench run --scale smoke --model deterministic-v1 --backend reference
cogmembench evaluate --run-id latest
cogmembench report --run-id latest
cogmembench export-trajectories --run-id latest
```

Its stateless, transcript, flat BM25, MindGraph passive, and MindGraph active-prefetch conditions
are compatibility coverage, not primary cognitive-v2 evidence.

## Artifacts

Runs write checkpointed JSONL to `results/raw`, evaluated rows to `results/evaluated`, traces to
`results/traces`, aggregate JSON and Markdown to `results/aggregated`, and compatibility-suite
trajectories to `results/trajectories`. Manifests record scenario and schedule hashes, prompt and
configuration hashes, repository state, conditions, capabilities, budgets, model identity, and
observable usage.
