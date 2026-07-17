# ADR-001: Standalone Python Harness with Explicit Backend Provenance

Status: accepted, 2026-07-15.

CogMemBench is a standalone Python package in `cogmembench/`, not embedded in an SDK. Scenario
generation, execution, providers, memory backends, evaluation, telemetry and reporting are
separate modules. Python was selected for provider orchestration and statistical/report work;
the actual local product path remains Rust server plus Python SDK/HTTP.

The harness has a deterministic `reference` backend for CI and an HTTP adapter for actual
MindGraph. Backend provenance is a mandatory result field. This allows cheap reproducibility
without misrepresenting an emulation as a product result.

Flat memory uses local BM25 over the same textual records. Active tools follow the existing
MCP action taxonomy while policy text derives from Hermes. HTTP instrumentation wraps every
request and snapshots state because graph event subscriptions are not currently exposed over
HTTP.

Alternatives rejected: extend LongMemEval (retrieval-centric and not treatment-controlled),
place the harness in `mindgraph-py` (couples experimental evolution to SDK releases), or use
cloud-only execution (not clean-room reproducible).
