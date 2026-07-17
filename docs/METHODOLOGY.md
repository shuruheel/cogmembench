# CogMemBench Methodology

CogMemBench estimates the causal effect of a memory treatment while holding the task, model,
sampling, step budget and non-memory tools fixed. It measures persistent reasoning and action
across separated sessions, not isolated recall.

## Unit of comparison

A trial is `(scenario_id, seed, model, condition)`. All conditions receive byte-identical
user and environment events. Hidden state, durable-memory annotations and scoring rules are
stored in evaluator-only scenario fields and are never rendered into model prompts. Results
are paired by scenario and seed.

The required conditions are:

- `stateless`: current session only; state is discarded at each session boundary.
- `transcript`: prior public turns are replayed; replay tokens are counted exactly.
- `flat`: untyped text records retrieved by auditable BM25 top-k.
- `flat-hybrid` (ablation): the same flat corpus with BM25/vector RRF using the same OpenAI
  embedding model configured for MindGraph.
- `mindgraph-passive`: structured persistent memory, predetermined retrieval, no memory tools.
- `mindgraph-active-prefetch`: the same backend plus MCP-compatible cognitive tools and the
  Hermes behavioral contract; predetermined retrieval remains enabled.
- `mindgraph-active-pull` (ablation): the same tools and session ingestion without predetermined
  retrieval, isolating model cognitive-tool policy from the faithful prefetch integration.

`oracle-policy` is an optional scripted upper bound. It uses the same structured backend and
invokes expected primitives at annotated durable transitions.

## Backends and evidence labels

`reference` is a deterministic in-process structured graph used for CI, evaluator tests and
cheap smoke runs. It emulates necessary semantics but is not MindGraph and its results are
never evidence for the product thesis. `mindgraph-local` and `mindgraph-cloud` use the actual
HTTP API and are reported separately. A run manifest records this label and rejects mixed
backends within a condition.

## Scenarios

The MVP has preference continuity, belief revision/contradiction, long-horizon project
continuation and failure learning. Each generator creates at least ten development variants.
A scenario contains public sessions, hidden world state, durable and non-durable expected
memories, expected revisions/task state, distractors and deterministic checks. Seeds control
names, values, ordering and distractors. Publication fixtures are held out from development.

Scales:

- `smoke`: one scenario per family and one seed, deterministic provider, all conditions.
- `development`: ten scenarios per family, three seeds where configured.
- `publication`: held-out variants and repeated model sampling; configuration is present but
  no publication claim is made by the MVP run.

## Execution

Each condition gets a fresh backend namespace. Session messages are delivered sequentially.
At a boundary, condition-specific persistence occurs. Before an evaluated turn, transcript,
flat retrieval or structured retrieval is injected according to treatment. Active memory
tools are available only in the active/oracle treatments. Provider failures are recorded per
trial; completed trials remain checkpointed and resume skips their stable trial IDs.

The deterministic CI provider follows observable scenario cues and exists to test the
harness. Real-provider adapters must return observable answers and tool calls only; hidden
chain-of-thought is never requested or saved.

## Evaluation

Deterministic checks take precedence: normalized expected facts/constraints, stale-value
absence, state/status fields, required and forbidden action markers, typed nodes/edges,
retrieval overlap and tool traces. Open-ended judging is optional and blind to condition
labels. Task success never rewards MindGraph vocabulary.

Answer equivalence uses a small, tested canonicalization vocabulary for dates, jurisdictions
and scenario-domain paraphrases. It does not use substring-only semantic scoring. Generator
tests verify that an advertised failure-recovery method is compatible with the failure mode;
ambiguous open-ended equivalence remains a human-audit item rather than an automatic pass.

Memory precision is useful durable writes divided by durable writes. Memory recall is
expected durable items captured divided by expected items. Contamination includes duplicate,
irrelevant, malformed or speculative committed records. Supersession and provenance are
separate checks. Retrieval precision/recall compare returned memory IDs against evaluator
annotations.

## Statistics

Reports expose every trial plus mean, median, sample standard deviation and bootstrap 95%
confidence intervals. Publication analysis uses paired condition differences and paired
standardized effect sizes; it reports scenario and seed variance, not only p-values. Composite
weights are explicit in configuration and category scores remain primary.

## Fairness and leakage controls

One run pins provider/model/version, temperature, token/step/tool budgets, timeouts, prompts,
embedding policy and scenario file hashes. The flat baseline uses the same text available to
structured conditions and an auditable BM25 implementation. Hidden fields are accessible
only to evaluators; agents receive a public view constructed by schema code. Prompt artifacts,
tool schemas, calls, retrievals and outputs are preserved.

## Interpretation

The experiment estimates effects under the tested integration and tool policy. It does not
establish that graphs generally outperform retrieval, that results transfer to other models,
or that a statistically uncertain development run is publication evidence. Failures and
negative paired deltas are first-class report sections.

## Recorded local/OpenRouter configuration

The first actual-backend run pinned `qwen/qwen3-32b`, temperature zero, DeepInfra-only routing,
provider fallbacks disabled, and reasoning disabled. The tested-agent adapter used OpenRouter's
`https://openrouter.ai/api/v1` base. The Rust chat client appends `/v1/chat/completions`, so the
local server used `https://openrouter.ai/api` as its base.

No embedding credential was configured. MindGraph retrieval used graph-aware
`/retrieve/context` with article/chunk limits set to zero and its FTS fallback. Automatic wiki
compilation was disabled because it adds a separate synthesis treatment and an unmetered LLM
call. A delayed reset probe was run after this setting and observed zero nodes and edges eight
seconds after clear. Provider and ingestion failures remain raw attempts; stable trial IDs let
resume append retries without overwriting evidence, and evaluation chooses the latest valid
attempt per trial.

The hybrid validation runs use `text-embedding-3-small` for both MindGraph and the flat
hybrid ablation. Startup refuses the run unless an explained query contains both FTS and
vector legs and delayed post-clear probes find no nodes, text hits, vector hits or embeddings.
Repository manifests include commit SHAs plus hashes indicating any dirty local overlay.
