# Cognitive Substrate Tranche 3

Status: adapter kit implemented; live MindGraph walking skeleton passed on 2026-07-16.

## Scope delivered

- Evidence-mode contract distinguishing native, mapped, and inadmissible sidecar state.
- Remote append-only operation journal with no evaluator dependence on local mirror state.
- Mapped adapters for MindGraph HTTP, Mem0 OSS REST, and Zep Cloud Graph API v2.
- Namespace-scoped reset for each system and asynchronous quiescence polling for Zep episodes.
- Declared-versus-observed portability audit with explicit absent, incorrect, and infrastructure
  states.
- External adapters wired into `validate-adapter-v2` and `run-cognitive-v2`, with a mandatory
  passing portability preflight before the runner schedules trials.
- Unit request-shape tests and opt-in live integration tests.

## Live evidence

A disposable MindGraph 1.9.0 server was compiled from the adjacent local checkout into `/tmp`,
started with an in-memory database, no LLM keys, and wiki autocompile disabled. The mapped adapter
passed the full behavioral portability contract. A three-family run crossing
`automatic-passive` and `agent-directed-active` then passed the runner's embedded portability
preflight and completed 6/6 valid trials.

This establishes MindGraph public-HTTP contract portability only. It is not a product-quality or
Gate 5 result.

## Remaining boundary

Mem0 and Zep live execution requires a configured self-hosted Mem0 service and Zep credentials.
Until those opt-in tests pass, Phase B's three-real-substrate exit and Gate 5 remain open.
