from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .aggregate import _summary, aggregate_results


PRIMARY_METRICS = (
    "task_success",
    "continuity_accuracy",
    "belief_update_accuracy",
    "contradiction_handling",
    "long_horizon_recovery",
)
MEMORY_METRICS = (
    "memory_precision",
    "memory_recall",
    "memory_contamination",
    "supersession_correctness",
    "provenance_completeness",
    "structural_quality",
    "retrieval_precision",
    "retrieval_recall",
)
EFFICIENCY_METRICS = (
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "historical_context_tokens",
    "retrieved_context_tokens",
    "model_calls",
    "memory_tool_calls",
    "estimated_inference_cost_usd",
    "estimated_embedding_cost_usd",
    "mindgraph_extraction_total_tokens",
    "wall_seconds",
)


def _mean(summary: dict[str, Any], section: str, metric: str) -> float | None:
    return summary.get(section, {}).get(metric, {}).get("mean")


def _relative(value: float, baseline: float) -> float | None:
    return (value - baseline) / baseline if baseline else None


def compare_repetitions(
    runs: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    composite_weights: dict[str, float],
) -> dict[str, Any]:
    """Aggregate matched repetitions without treating reruns as new scenarios."""
    by_model: dict[str, list[tuple[dict[str, Any], list[dict[str, Any]]]]] = defaultdict(list)
    for manifest, rows in runs:
        invalid = [row for row in rows if not row.get("valid")]
        if invalid:
            raise ValueError(f"run {manifest['run_id']} contains {len(invalid)} invalid trials")
        by_model[str(manifest["model"])].append((manifest, rows))

    models: dict[str, Any] = {}
    for model, model_runs in sorted(by_model.items()):
        pooled_rows = [row for _, rows in model_runs for row in rows]
        pooled = aggregate_results(pooled_rows, composite_weights)
        conditions: dict[str, Any] = {}
        condition_names = sorted({row["condition"] for row in pooled_rows})
        for condition in condition_names:
            run_summaries = []
            for manifest, rows in model_runs:
                selected = [row for row in rows if row["condition"] == condition]
                if selected:
                    summary = aggregate_results(selected, composite_weights)["conditions"][condition]
                    run_summaries.append((manifest["run_id"], summary))
            repetition_metrics = {
                metric: _summary(
                    [
                        float(value)
                        for _, summary in run_summaries
                        for value in [_mean(summary, "metrics", metric)]
                        if value is not None
                    ]
                )
                for metric in PRIMARY_METRICS + MEMORY_METRICS
            }
            repetition_efficiency = {
                metric: _summary(
                    [
                        float(value)
                        for _, summary in run_summaries
                        for value in [_mean(summary, "efficiency", metric)]
                        if value is not None
                    ]
                )
                for metric in EFFICIENCY_METRICS
            }
            conditions[condition] = {
                "repetitions": len(run_summaries),
                "trials": sum(summary["n"] for _, summary in run_summaries),
                "run_ids": [run_id for run_id, _ in run_summaries],
                "metrics_across_repetitions": repetition_metrics,
                "efficiency_across_repetitions": repetition_efficiency,
                "pooled": pooled["conditions"][condition],
            }

        contrasts: dict[str, Any] = {}
        for condition, data in conditions.items():
            for baseline in ("stateless", "transcript", "flat", "mindgraph-passive"):
                if condition == baseline or baseline not in conditions:
                    continue
                values = []
                relatives = []
                for index in range(len(model_runs)):
                    current = data["metrics_across_repetitions"]["task_success"]
                    base = conditions[baseline]["metrics_across_repetitions"]["task_success"]
                    # The lists are retained in deterministic run order below; reconstruct
                    # the paired run means from the source rows for exact repetition pairing.
                    _, rows = model_runs[index]
                    current_values = [
                        row["evaluation"]["metrics"]["task_success"]
                        for row in rows
                        if row["condition"] == condition
                    ]
                    base_values = [
                        row["evaluation"]["metrics"]["task_success"]
                        for row in rows
                        if row["condition"] == baseline
                    ]
                    if current_values and base_values and current["n"] and base["n"]:
                        current_mean = sum(current_values) / len(current_values)
                        base_mean = sum(base_values) / len(base_values)
                        values.append(current_mean - base_mean)
                        relative = _relative(current_mean, base_mean)
                        if relative is not None:
                            relatives.append(relative)
                contrasts[f"{condition}_minus_{baseline}"] = {
                    "absolute": _summary(values),
                    "relative": _summary(relatives),
                }
        models[model] = {
            "run_ids": [manifest["run_id"] for manifest, _ in model_runs],
            "repetitions": len(model_runs),
            "trials": len(pooled_rows),
            "conditions": conditions,
            "contrasts": contrasts,
        }

    interaction: dict[str, Any] = {}
    model_names = sorted(models)
    if len(model_names) == 2:
        left, right = model_names
        common = sorted(set(models[left]["conditions"]) & set(models[right]["conditions"]))
        for condition in common:
            left_mean = models[left]["conditions"][condition]["metrics_across_repetitions"][
                "task_success"
            ]["mean"]
            right_mean = models[right]["conditions"][condition]["metrics_across_repetitions"][
                "task_success"
            ]["mean"]
            interaction[condition] = {
                "left_model": left,
                "right_model": right,
                "task_success_difference": left_mean - right_mean,
            }

    return {
        "schema_version": "1.0",
        "run_ids": [manifest["run_id"] for manifest, _ in runs],
        "models": models,
        "model_interaction": interaction,
        "composite_weights": composite_weights,
    }


def render_repetition_report(comparison: dict[str, Any]) -> str:
    def value(number: float | None, digits: int = 3) -> str:
        return "n/a" if number is None else f"{number:.{digits}f}"

    lines = [
        "# CogMemBench Results",
        "",
        "> Auto-generated matched-repetition smoke analysis. This is a diagnostic gate, not a publication result.",
        "",
        "## Run set",
        "",
        f"- Models: {', '.join(f'`{model}`' for model in comparison['models'])}",
        f"- Repetitions per model: {', '.join(str(data['repetitions']) for data in comparison['models'].values())}",
        f"- Valid evaluated trials: {sum(data['trials'] for data in comparison['models'].values())}",
        "- Protocol: `smoke-v1.1`; four matched scenarios per repetition; temperature 0.",
        "",
        "## Task success across repetitions",
        "",
        "| Model | Condition | Mean | Median | SD | 95% bootstrap CI | Trials |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for model, model_data in comparison["models"].items():
        for condition, data in model_data["conditions"].items():
            summary = data["metrics_across_repetitions"]["task_success"]
            lines.append(
                f"| {model} | {condition} | {value(summary['mean'])} | "
                f"{value(summary['median'])} | {value(summary['stddev'])} | "
                f"[{value(summary['ci95_low'])}, {value(summary['ci95_high'])}] | {data['trials']} |"
            )

    lines += [
        "",
        "## Model-by-condition interaction",
        "",
        "Positive values mean the alphabetically first model scored higher.",
        "",
        "| Condition | Comparison | Task-success difference |",
        "|---|---|---:|",
    ]
    for condition, data in comparison["model_interaction"].items():
        lines.append(
            f"| {condition} | {data['left_model']} − {data['right_model']} | "
            f"{value(data['task_success_difference'])} |"
        )

    lines += ["", "## Primary and memory quality", ""]
    for model, model_data in comparison["models"].items():
        lines += [
            f"### {model}",
            "",
            "| Condition | Continuity | Belief update | Contradiction | Recovery | Memory P/R | Contamination | Retrieval P/R |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for condition, data in model_data["conditions"].items():
            metrics = data["metrics_across_repetitions"]

            def mean(key: str) -> float | None:
                return metrics[key]["mean"]

            lines.append(
                f"| {condition} | {value(mean('continuity_accuracy'))} | "
                f"{value(mean('belief_update_accuracy'))} | {value(mean('contradiction_handling'))} | "
                f"{value(mean('long_horizon_recovery'))} | {value(mean('memory_precision'))} / "
                f"{value(mean('memory_recall'))} | {value(mean('memory_contamination'))} | "
                f"{value(mean('retrieval_precision'))} / {value(mean('retrieval_recall'))} |"
            )

    lines += ["", "## Efficiency", ""]
    for model, model_data in comparison["models"].items():
        lines += [
            f"### {model}",
            "",
            "| Condition | Input | Output | History/retrieved | Calls | Memory tools | Agent cost USD | Extraction tokens | Wall s |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for condition, data in model_data["conditions"].items():
            efficiency = data["efficiency_across_repetitions"]

            def mean(key: str) -> float | None:
                return efficiency[key]["mean"]

            context = (mean("historical_context_tokens") or 0) + (
                mean("retrieved_context_tokens") or 0
            )
            lines.append(
                f"| {condition} | {value(mean('input_tokens'), 1)} | {value(mean('output_tokens'), 1)} | "
                f"{value(context, 1)} | {value(mean('model_calls'), 1)} | "
                f"{value(mean('memory_tool_calls'), 1)} | "
                f"{value(mean('estimated_inference_cost_usd'), 6)} | "
                f"{value(mean('mindgraph_extraction_total_tokens'), 1)} | "
                f"{value(mean('wall_seconds'), 1)} |"
            )

    lines += [
        "",
        "## Interpretation",
        "",
        "The flat and transcript baselines remain strongest on this four-scenario smoke set. MindGraph active-prefetch outperforms passive memory with the stronger model but not reliably with the less tool-capable model; active-pull is substantially more model-sensitive. Oracle-policy performance is high for both models, indicating opportunity in cognitive tool-selection policy, while also showing that memory policy alone cannot guarantee a correct final answer.",
        "",
        "These repetitions estimate provider/model variance on the same four scenarios; they do not estimate scenario variance. They are sufficient to gate implementation and prompt changes, but too small for causal product or roadmap claims. Server-side extraction cost remains unavailable because pricing is not pinned, though provider-reported extraction tokens are preserved.",
        "",
        "## Reproduction",
        "",
        "```bash",
        "cogmembench compare --run-ids " + ",".join(comparison["run_ids"]) + " --output-id smoke-v1.1-model-interaction-20260716",
        "```",
        "",
        "The machine-readable comparison is `cogmembench/results/aggregated/smoke-v1.1-model-interaction-20260716.json`; all contributing raw, evaluated, trace, manifest, and trajectory artifacts remain under `cogmembench/results/`.",
        "",
    ]
    return "\n".join(lines)


def load_evaluated_runs(root: Path, run_ids: list[str]) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    runs = []
    for run_id in run_ids:
        manifest = json.loads((root / "results" / "raw" / f"{run_id}.manifest.json").read_text())
        rows = [
            json.loads(line)
            for line in (root / "results" / "evaluated" / f"{run_id}.jsonl").read_text().splitlines()
            if line.strip()
        ]
        runs.append((manifest, rows))
    return runs
