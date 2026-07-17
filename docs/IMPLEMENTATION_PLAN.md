# Implementation Plan

1. Freeze schema, public/evaluator separation, condition contracts, metrics and configs.
2. Implement deterministic generators for four MVP families and three scales.
3. Implement checkpointed runner, deterministic and OpenAI-compatible providers, five
   conditions, reference/flat/MindGraph HTTP memory, and structured event traces.
4. Implement deterministic outcome, graph-quality and tool-policy evaluators.
5. Implement aggregation, bootstrap paired analysis, Markdown/JSON/plot reporting and
   normalized cognitive trajectory export without chain-of-thought.
6. Test determinism, condition delivery, isolation, reset contamination, metrics, accounting,
   failures, traces, reports, leakage and resume. Add CI smoke.
7. Run smoke, development, targeted failures and any credential-supported real provider plus
   actual MindGraph comparison. Clearly label infeasible runs and do not substitute mocks.
