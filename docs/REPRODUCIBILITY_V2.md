# Cognitive-v2 reproducibility package

The package is credential-free through deterministic and local-reference validation. Provider and
hosted-substrate executions require the separately documented credentials.

## Local validation

```bash
python3 -m pytest -q
ruff check .

cogmembench generate --scale calibration --seed 42 --generator-version cognitive-v2 \
  --output scenarios/fixtures/cognitive-v2-calibration-42.jsonl
cogmembench validate-cognitive-v2 --scenarios scenarios/fixtures/cognitive-v2-calibration-42.jsonl
cogmembench validate-generators-v2 --scenarios scenarios/fixtures/cognitive-v2-calibration-42.jsonl
cogmembench validate-counterfactuals-v2 --scenarios scenarios/fixtures/cognitive-v2-calibration-42.jsonl
cogmembench validate-evaluators-v2
```

## Deterministic treatment and analysis

```bash
cogmembench run-cognitive-v2 \
  --scenarios scenarios/fixtures/cognitive-v2-calibration-42.jsonl \
  --model deterministic-v1 --adapter reference --run-id local-v2
cogmembench analyze-cognitive-v2 --evaluated results/evaluated/local-v2.jsonl \
  --output results/aggregated/local-v2-analysis.json
cogmembench failures-cognitive-v2 --evaluated results/evaluated/local-v2.jsonl
cogmembench cost-cognitive-v2 --evaluated results/evaluated/local-v2.jsonl --profile lite
cogmembench power-cognitive-v2 --evaluated results/evaluated/local-v2.jsonl \
  --treatment automatic-passive --baseline transcript --minimum-effect 0.10 --assumed-sd 0.30
```

Deterministic scores test plumbing and gold consistency only. They are not model/substrate quality
evidence and cannot finalize power or difficulty.

Natural-mode runs use the same command with `--operating-mode natural` plus the exact frozen,
vendor-reviewed `--retrieval-k` and `--retrieval-tokens`. Matched comparisons retain the default
`--operating-mode matched-budget`. Never pool the two labels.

## Independent annotation packet

```bash
cogmembench export-cognitive-v2-annotations \
  --scenarios scenarios/held_out/publication-v2.jsonl --sample-size 50 \
  --output reviews/blinded-packet.json --answer-key reviews/answer-key.json

cogmembench agreement-cognitive-v2 \
  --annotations reviews/completed-annotations.jsonl \
  --answer-key reviews/answer-key.json --kappa-threshold 0.8 \
  --gold-accuracy-threshold 0.9 --output reviews/agreement.json
```

The answer key must not be shared with annotators. A generated packet is infrastructure, not a
completed human-validity result.

## Release and freeze

```bash
cogmembench prepare-cognitive-v2-release \
  --scenarios scenarios/held_out/newly-generated.jsonl --split publication \
  --reference development=scenarios/fixtures/cognitive-v2-calibration-42.jsonl \
  --output scenarios/held_out/publication-v2.jsonl

# Replace model snapshots and paths in a copy of the example first.
cogmembench freeze-cognitive-v2-protocol \
  --spec configs/cognitive_v2_freeze.example.json \
  --output configs/protocols/cognitive-v2-publication.json
cogmembench freeze-cognitive-v2-protocol \
  --verify configs/protocols/cognitive-v2-publication.json
```

Never freeze the checked-in example unchanged. Publication release creation, independent human
agreement, vendor review, cost-complete projection, and frozen-pilot power must all pass first.

## Required publication bundle

Include the protocol freeze and release manifest; exact scenario file; raw/evaluated rows; complete
observable traces; retry/invalid rows; adapter/capability/cost manifests; model snapshot IDs;
analysis JSON; annotation agreement report; vendor-review registry; environment/package lock; and
the append-only iteration log. Do not publish credentials, hidden chain-of-thought, or proprietary
provider internals.

Software is Apache-2.0; generated scenario and dataset artifacts are CC BY 4.0. Preserve the
applicable license and attribution when redistributing the publication bundle.
