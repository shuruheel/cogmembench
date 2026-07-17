# Cognitive Substrate Tranche 4

Status: local baseline matrix implemented on 2026-07-17.

## Scope delivered

- Actual Okapi BM25 (`k1=1.5`, `b=0.75`) replaced the former term-overlap flat ranking.
- Deterministic rolling extractive summary with a manifest-frozen token ceiling.
- Standalone dense-vector retrieval over the shared canonical artifact rendering.
- BM25/vector reciprocal-rank fusion with fixed `rrf_k=60` and per-result scoring legs.
- Explicit retrieval representation and scoring metadata in passive traces and active tool output.
- Complete harness-side embedding-call, token, model, and storage accounting.
- A full-transcript ceiling separated from the token-matched transcript baseline.
- Runner/CLI adapter selection, mandatory portability preflight, configuration, and smoke tests.

All four adapters passed their mandatory preflight and completed 3/3 valid
`automatic-passive` trials across the three core families (12/12 total) with identical scenario
and schedule hashes. These deterministic runs validate the harness, not baseline quality.

## Fairness contract

`transcript` and persistent retrieval treatments share `matched_context_tokens`, including
scenario-declared checkpoint overrides. `transcript-full` has no benchmark read ceiling and is
reported as a ceiling rather than a deployment-matched baseline. BM25, vector, and hybrid index
the identical fixed canonical rendering; hybrid changes only ranking fusion. Run manifests freeze
the item and token budgets, adapter manifest, embedding identity, and preflight usage.

## Evidence boundary

The deterministic feature-hashing provider makes vector and hybrid contract tests credential-free
but is not semantic-baseline evidence. Real-model vector/hybrid experiments require a pinned
OpenAI-compatible embedding endpoint and record its identity and usage. The summary baseline is
extractive, not an LLM-generated summary comparison. Per-substrate oracle capture and
publication-scale calibration remain open.

Mem0 and Zep live credentials are intentionally reserved for final integration, as requested.
