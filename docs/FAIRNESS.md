# Fairness, Isolation and Leakage

Conditions share model/provider settings, public task data, environment tools, maximum steps,
timeouts and seeds. Only persistence, retrieval and memory tools differ. Transcript replay
and retrieved context tokens are separately measured. Flat and structured memory receive the
same public textual evidence; no condition receives evaluator annotations.

Every trial uses a new namespace and starts with a sentinel reset test. Reset validation
writes corpus A, clears/destroys it, writes corpus B, and searches all supported retrieval
modes for A. A hit invalidates the backend. Snapshots include node/edge counts and stable
content hashes before and after a trial.

Generated JSON has an explicit `public` view and an `evaluator` view. Runner code accepts
only `PublicScenario`; evaluator code joins hidden records after execution. A regression test
inspects serialized model requests for hidden keys and expected-answer strings.

Real comparisons must use a single backend label and embedding configuration. Cloud and local
results are never pooled without stratification. Failed ingestion, reset or trace capture
marks a trial invalid rather than silently degrading to another condition.
