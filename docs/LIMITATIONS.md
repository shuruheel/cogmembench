# Limitations

- Deterministic smoke/development runs validate harness behavior, not language-model ability.
- The reference structured backend is not MindGraph and cannot support product claims.
- Actual session extraction and vector retrieval require configured providers.
- HTTP instrumentation observes request timing and snapshots, not internal database timing.
- BM25 uses fixed, auditable Okapi parameters (`k1=1.5`, `b=0.75`); it is not tuned per family.
- The credential-free vector provider is deterministic feature hashing for contract and CI runs.
  It is not a semantic embedding model and its scores are not scientific vector-baseline evidence.
  Real vector/hybrid runs require a pinned embedding endpoint and model.
- The rolling summary baseline is deterministic and extractive. It retains canonical source
  artifacts for temporal filtering and conformance, and does not represent the quality or cost of
  an LLM-generated hierarchical summary.
- The four schema-v1 families are compatibility coverage, not cognitive-substrate publication
  evidence. Cognitive v2 now has oracle and agent-facing treatment paths for all three core
  families. A 450-world publication-shaped mechanical release rehearsal passes, but live external
  portability, representative-model calibration, and the frozen publication study remain
  incomplete.
- Exact deterministic checks can miss stylistic or nuanced reasoning quality; optional LLM
  judging is not enabled in CI.
- The evaluator equivalence policy intentionally recognizes only registered, bounded
  paraphrases and leading uncertainty phrases. It rejects ambiguous alternatives and negation,
  but cannot establish broad natural-language equivalence without the planned blind human audit.
- The procedural generators expose three controlled tiers and passed a 450-scenario mechanical
  uniqueness rehearsal. Those tiers vary structural burden, but their empirical difficulty has
  not yet been calibrated on representative models. The realizations also come from one generator
  implementation rather than multiple independent authors.
- The ablation adapter removes canonical benchmark features consistently, but does not prove that
  a vendor's native feature toggle is equivalent. Vendor-native and canonical-wrapper ablations
  must be reported separately. Only one feature is removed per run to preserve causal
  interpretability.
- `no-lesson-consolidation` has no opportunity in the current three-family core. Recursive
  failure amplification now exists, but uses one forensic cross-wiring correction pattern; it
  still needs independently authored and lexically broader realizations.
- Nested-bootstrap intervals are world-first and protect against checkpoint inflation, but they
  cannot rescue sparse or unbalanced pilot data. Intervals may collapse when a stratum has no
  within-stratum variation. The mixed-effects formula is recorded but not yet fitted.
- Development-scale confidence intervals are diagnostic. Publication claims require held-out
  scenarios, real models, repeated sampling and human audit.
- The cognitive-v2 reference executor uses oracle capture to validate the ledger, clock, snapshot,
  repair, and evaluator contracts. Its perfect score is a mechanical ceiling and says nothing
  about automatic capture, retrieval policy, model reasoning, or MindGraph quality.
- The current automatic reference treatment stores public events and model outputs directly; it
  validates treatment plumbing, not production extraction quality. The agent-directed CI policy
  is deliberately simple and should not be interpreted as an optimized cognitive policy.
- `oracle-passive` replays canonical gold operations into the selected substrate. This isolates
  capture quality from retrieval/storage quality, but mapped external adapters still test the
  canonical journal representation rather than proving native ontology equivalence.
- Steering localization is causal only at the treatment-bundle level. For example,
  oracle-minus-automatic can implicate capture or organization but cannot separate those stages
  by itself; the implemented single-feature ablations are needed for finer attribution and still
  do not establish interactions among removed features.
- External mapped journals establish contract portability but do not prove that a vendor's
  native ontology, temporal query engine, or dependency semantics implement the canonical
  operations. Native and mapped evidence must remain stratified in reports.
- The MindGraph live walking skeleton used an in-memory 1.9.0 server without LLM extraction or
  embeddings. It validates scoped reset, remote persistence, text retrieval, revision replay,
  snapshot reconstruction, and audit export—not production automatic extraction quality.
- Mem0 OSS, Zep Cloud, and Cognee request mappings are covered by deterministic fake-service
  tests, but no live service or credential was available in this tranche. Their portability
  status remains unverified until the opt-in live tests pass.
- The built-in publication holdout pack changes causal structure and realization identifiers, but
  is implementation-team-authored and explicitly marked non-independent. It cannot satisfy the
  independently authored realization requirement or replace the blinded human audit.
- Cost reports refuse to silently price unknown external inference, embedding, or hosting at zero.
  Consequently, external projections remain lower bounds until those services expose or provide
  complete billable usage.

## Hybrid and strong-model smoke runs

- `smoke-hybrid-qwen-20260716` and `smoke-hybrid-gpt54mini-20260716` are diagnostic smoke
  runs with four scenarios each. They verify true FTS/vector retrieval but are too small for
  roadmap or publication claims.
- The strong model used memory tools and explicitly retrieved in every active trial. Its
  active-condition failures therefore cannot be attributed solely to an inability to emit
  tool calls; retrieval quality, tool-result interpretation, graph pollution and integration
  policy remain live explanations.
- Trace audit found brittle wording in the initial failure-learning evaluator and a generator
  that advertised a parser inconsistent with its delimiter. Those artifacts are retained as
  debug evidence, but a corrected clean rerun is required before treating their task scores
  as benchmark results.
- The clean smoke trace audit added deterministic equivalences for an explicit superseding
  preference update, CSV/quoted-delimited parser terminology, and explicit exclusion of
  fixed-width binary data. The raw rows preserve their run-time pre-audit evaluations; the
  generated report is a deterministic post-audit rescore of the unchanged model outputs.
  These rules are locked by tests before any development run, but the adjustment was informed
  by smoke outputs and must be disclosed as benchmark-development iteration.
- Tested-agent and flat-hybrid embedding costs are measured. MindGraph extraction-model and
  server-side embedding token usage/cost remain unavailable, so total treatment cost is a
  lower bound even though wall time includes those operations.
- OpenRouter's `openai/gpt-5.4-mini` alias was provider-pinned but not snapshot-pinned. Model
  and provider identifiers are recorded; exact publication reproducibility requires a stable
  snapshot identifier if OpenRouter exposes one.
- The first Qwen active-pull artifact predates explicit tool-result context-token accounting;
  its total provider input is valid, but its retrieved-context subtotal is understated. The
  strong-model run and subsequent runs use the corrected accounting.

## First OpenRouter/local run

- `smoke-openrouter-local-debug2-20260715` contains four scenarios and 20 matched valid
  trials. Its confidence intervals are descriptive; it is not publication evidence and no
  real-model development run has been completed.
- The local server had no OpenAI embedding key. MindGraph context retrieval therefore used
  its documented FTS fallback. This run does not measure vector/hybrid MindGraph retrieval.
- The reported cost covers tested-agent OpenRouter calls only. Server-side extraction made
  additional OpenRouter calls whose token usage and cost are not exposed by the HTTP API.
- Five initial attempts timed out or had transient connection resets. Raw JSONL preserves all
  25 attempts; resume produced one latest valid attempt for each of the 20 stable trial IDs.
- `temperature=0` does not eliminate provider/model variance. Publication runs need repeated
  matched executions and should separate scenario variance from provider variance.
- Active memory made useful writes but never invoked explicit retrieval: appropriate retrieval
  was 0 and missed retrieval was 1.0. This is evidence about the tested Qwen tool policy, not a
  general upper bound on active cognitive memory.
- Session extraction created roughly 145--153 nodes plus edges per scenario on average. The
  resulting memory recall was high but precision was below 0.10, so graph growth and memory
  pollution remain major failure modes.
- The server's automatic wiki task is registered as a job but can finish a graph write after
  `/clear` has cancelled jobs and returned. A live probe reproduced a post-reset Article write.
  The benchmark run therefore set `MINDGRAPH_WIKI_AUTOCOMPILE=off`; wiki synthesis is not part
  of Conditions D/E. The server lifecycle bug remains a documented core limitation.
- A separate reset race was found in detached automatic embedding writes: an embedding request
  started before `/clear` could finish afterward and recreate an orphan embedding row. The
  local core now invalidates in-flight auto-embedding generations on clear and has a blocked-
  provider regression test. Repeated delayed contamination probes passed after the fix.
