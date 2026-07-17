# Cognitive Tool-Use Training Data

`cogmembench export-trajectories --run-id <id>` converts active/oracle observable traces to
JSONL. It never stores hidden chain-of-thought. Each row contains the scenario/session/turn,
observable cognitive state, available tools, selected tool and arguments, returned observation,
graph delta and evaluator annotations.

The export supports:

- supervised fine-tuning on useful tool selections and well-formed arguments;
- preference pairs between useful and redundant/harmful/missed operations;
- tool-selection policy training from pre-action observable state;
- process-reward models using primitive correctness, write quality and downstream outcomes;
- negative examples built from missed retrievals, stale-belief writes, redundant records and
  premature commitment.

The first credible experiment is a small tool-policy adapter trained only on high-confidence
active/oracle transitions, with scenario families split by generated identity/value templates.

Current active-run exports deliberately leave step-level `useful`, `primitive_correct`, and
`write_quality` labels null. Trial-level metrics are included as context but are not copied
onto individual actions. A human or deterministic transition annotator must label redundant,
premature, harmful and missed operations before the data are used for supervised or preference
training. The observable schema is ready; the smoke corpus and its process labels are not.
Evaluate it on held-out generator seeds against the same base model without the adapter. Do not
train on evaluator hidden state or deterministic-provider traces.

Current gaps: the real-model smoke run contains only 63 active tool calls across four scenarios.
There is no human-audited preference-pair set, no oracle trajectory, and passive extraction
mutations are reconstructed from snapshots rather than streamed from an HTTP event API. Those
gaps should be closed before even a small cognitive-tool-use fine-tune.
