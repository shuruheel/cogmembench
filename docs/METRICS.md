# Metrics

CogMemBench reports disaggregated metrics. Missing provider measurements are `null`, never
fabricated.

## Outcome

`task_success`, `continuity_accuracy`, `belief_update_accuracy`,
`contradiction_handling`, and `long_horizon_recovery` are normalized to `[0,1]` from explicit
scenario checks. Duplicate work rate is repeated completed action markers divided by all
action markers.

## Memory and retrieval

`memory_precision`, `memory_recall`, `memory_contamination`, `supersession_correctness`,
`provenance_completeness`, `structural_quality`, `retrieval_precision`, and
`retrieval_recall` are computed from memory snapshots and trace IDs. Structural quality is
diagnostic: it cannot increase task success merely because a response uses typed nodes.
Expected durable memories are matched one-to-one with graph records, so one broad summary
cannot satisfy several expected memories. Supersession requires an exact new-to-old
`Supersedes` edge (or an exact `superseded_by` reference); provenance requires source fields
or evidence/source edges connected to the matched record.

## Efficiency

The harness records input, output, provider-reported reasoning, historical/retrieved context
tokens, calls, tool calls by type, wall latency, configured price estimate, graph bytes/node/
edge growth and duplicate work. The default tokenizer is a deterministic Unicode word/punctuation
counter; real providers may additionally supply authoritative token usage. Harness-side
flat-hybrid embedding calls, input tokens, latency and configured cost are reported separately.
MindGraph server-side extraction and embedding usage remains unavailable until the server
exposes it and is never silently included as zero cost. Reports identify the accounting source.

## Tool policy

Expected opportunities in evaluator annotations are matched to observable tool traces:
appropriate/missed/unnecessary retrieval, appropriate/missed/redundant/harmful write, and
correct primitive selection. Rates use opportunity counts as denominators and are null when
the condition has no memory tools.

## Optional composite

The default composite is
`0.30 task_success + 0.20 continuity + 0.15 belief_update + 0.10 contradiction + 0.10 recovery + 0.05 memory_precision + 0.05 memory_recall + 0.05 (1-contamination)`.
Weights live in `configs/metrics.yaml`, are printed in every report, and may be changed before
a run but not after observing its results.
