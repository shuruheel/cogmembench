from __future__ import annotations

from typing import Any


def _v(value: Any, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render_development_v2_report(
    aggregate: dict[str, Any], manifest: dict[str, Any]
) -> str:
    conditions = aggregate["conditions"]
    lines = [
        "# CogMemBench Development Results",
        "",
        "> Auto-generated from frozen `development-mvp-v2` raw and evaluated artifacts.",
        "",
        "## Treatment",
        "",
        f"- Run ID: `{manifest['run_id']}`",
        f"- Model: `{manifest['model']}` via `{manifest['provider']}`",
        f"- Backend: `{manifest['backend']}`",
        f"- Scenarios: {manifest['scenario_count']}; completed trials: {manifest.get('completed_trials', 0)}",
        f"- Protocol lock: `{manifest.get('protocol_lock', {}).get('protocol_id')}`",
        f"- Schedule: `{manifest.get('schedule', {}).get('version')}` / `{manifest.get('schedule', {}).get('sha256')}`",
        "",
        "## Primary outcomes",
        "",
        "Metrics are family-scoped; `n/a` means the metric does not apply to that task family.",
        "",
        "| Condition | n | Task success | Continuity | Belief update | Contradiction | Recovery | Composite |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, data in conditions.items():
        metrics = data["metrics"]
        lines.append(
            f"| {name} | {data['n']} | {_v(metrics.get('task_success', {}).get('mean'))} | "
            f"{_v(metrics.get('continuity_accuracy', {}).get('mean'))} | "
            f"{_v(metrics.get('belief_update_accuracy', {}).get('mean'))} | "
            f"{_v(metrics.get('contradiction_handling', {}).get('mean'))} | "
            f"{_v(metrics.get('long_horizon_recovery', {}).get('mean'))} | "
            f"{_v(data['composite']['mean'])} |"
        )

    lines += ["", "## Task-family outcomes", ""]
    for family, family_data in aggregate.get("by_family", {}).items():
        lines += [
            f"### {family}",
            "",
            "| Condition | Mean | Median | SD | 95% bootstrap CI |",
            "|---|---:|---:|---:|---:|",
        ]
        for condition, summary in family_data.items():
            lines.append(
                f"| {condition} | {_v(summary['mean'])} | {_v(summary['median'])} | "
                f"{_v(summary['stddev'])} | [{_v(summary['ci95_low'])}, {_v(summary['ci95_high'])}] |"
            )

    lines += [
        "",
        "## Memory and retrieval quality",
        "",
        "| Condition | Memory P/R | Contamination | Supersession | Provenance | Structural | Retrieval P/R |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, data in conditions.items():
        metrics = data["metrics"]
        lines.append(
            f"| {name} | {_v(metrics.get('memory_precision', {}).get('mean'))} / "
            f"{_v(metrics.get('memory_recall', {}).get('mean'))} | "
            f"{_v(metrics.get('memory_contamination', {}).get('mean'))} | "
            f"{_v(metrics.get('supersession_correctness', {}).get('mean'))} | "
            f"{_v(metrics.get('provenance_completeness', {}).get('mean'))} | "
            f"{_v(metrics.get('structural_quality', {}).get('mean'))} | "
            f"{_v(metrics.get('retrieval_precision', {}).get('mean'))} / "
            f"{_v(metrics.get('retrieval_recall', {}).get('mean'))} |"
        )

    lines += [
        "",
        "## Cognitive tool policy",
        "",
        "| Condition | Appropriate retrieve | Missed retrieve | Unnecessary retrieve | Appropriate write | Missed write | Harmful write | Redundant write | Primitive selection |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, data in conditions.items():
        metrics = data["metrics"]
        lines.append(
            f"| {name} | {_v(metrics.get('appropriate_retrieval_rate', {}).get('mean'))} | "
            f"{_v(metrics.get('missed_retrieval_rate', {}).get('mean'))} | "
            f"{_v(metrics.get('unnecessary_retrieval_rate', {}).get('mean'))} | "
            f"{_v(metrics.get('appropriate_write_rate', {}).get('mean'))} | "
            f"{_v(metrics.get('missed_write_rate', {}).get('mean'))} | "
            f"{_v(metrics.get('harmful_write_rate', {}).get('mean'))} | "
            f"{_v(metrics.get('redundant_write_rate', {}).get('mean'))} | "
            f"{_v(metrics.get('correct_primitive_selection', {}).get('mean'))} |"
        )

    lines += [
        "",
        "## Token efficiency by phase",
        "",
        "Construction tokens are one-time write-side costs. Read-context tokens are replayed or retrieved context presented during agent operation. Lifecycle tokens include tested-agent input/output plus measured construction tokens.",
        "",
        "| Condition | Agent tokens | Read context | Construction | Lifecycle | Success / 1k read | Tokens / success | Source/read compression | Agent cost USD | Wall s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, data in conditions.items():
        efficiency = data["efficiency"]
        metrics = data["metrics"]
        lines.append(
            f"| {name} | {_v(efficiency.get('agent_total_tokens', {}).get('mean'), 1)} | "
            f"{_v(efficiency.get('read_context_tokens', {}).get('mean'), 1)} | "
            f"{_v(efficiency.get('memory_construction_tokens', {}).get('mean'), 1)} | "
            f"{_v(efficiency.get('lifecycle_tokens', {}).get('mean'), 1)} | "
            f"{_v(metrics.get('task_success_per_1k_read_tokens', {}).get('mean'))} | "
            f"{_v(metrics.get('tokens_per_success', {}).get('mean'), 1)} | "
            f"{_v(metrics.get('context_compression_ratio', {}).get('mean'))} | "
            f"{_v(efficiency.get('estimated_inference_cost_usd', {}).get('mean'), 6)} | "
            f"{_v(efficiency.get('wall_seconds', {}).get('mean'), 1)} |"
        )

    lines += [
        "",
        "## Reuse checkpoints",
        "",
        "| Condition | First-use success | Second-use success |",
        "|---|---:|---:|",
    ]
    for condition, points in aggregate.get("reuse", {}).items():
        lines.append(
            f"| {condition} | {_v(points.get('1', {}).get('mean'))} | "
            f"{_v(points.get('2', {}).get('mean'))} |"
        )

    lines += [
        "",
        "## Amortized memory-context tokens",
        "",
        "These are descriptive break-even projections using measured construction tokens plus the observed mean read-context cost per evaluation checkpoint.",
        "",
        "| Condition | q=1 | q=5 | q=10 | q=25 |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, data in conditions.items():
        efficiency = data["efficiency"]
        construction = efficiency.get("memory_construction_tokens", {}).get("mean") or 0
        read = efficiency.get("read_context_tokens", {}).get("mean") or 0
        checkpoints = efficiency.get("evaluation_checkpoints", {}).get("mean") or 1
        per_use = read / checkpoints
        projected = [construction + count * per_use for count in (1, 5, 10, 25)]
        lines.append(
            f"| {name} | " + " | ".join(_v(value, 1) for value in projected) + " |"
        )

    lines += [
        "",
        "## Paired differences versus stateless",
        "",
        "| Condition | Mean delta | 95% family-stratified bootstrap CI | Standardized paired effect |",
        "|---|---:|---:|---:|",
    ]
    for name, data in aggregate["paired"].items():
        delta = data["task_success_delta_vs_stateless"]
        effect = data["paired_standardized_effect"]
        effect_text = (
            "infinite (zero variance)"
            if effect in (float("inf"), float("-inf"))
            else _v(effect)
        )
        lines.append(
            f"| {name} | {_v(delta['mean'])} | "
            f"[{_v(delta['ci95_low'])}, {_v(delta['ci95_high'])}] | {effect_text} |"
        )

    lines += ["", "## Failure analysis", ""]
    failures = aggregate.get("failures", [])
    if not failures:
        lines.append("No deterministic task failures.")
    for failure in failures[:40]:
        lines.append(
            f"- `{failure['scenario_id']}` / `{failure['condition']}`: "
            f"task success {_v(failure['score'])}."
        )

    lines += [
        "",
        "## Limitations",
        "",
        "This development run supports claims only for the pinned model, prompts, production MCP contract, local server binary, scenario generator, and synchronous session-ingestion policy in its manifest. The two-checkpoint reuse curve is empirical; q=5/10/25 values are projections. Server embedding token usage and database-only latency remain unavailable. Composite scores are secondary and reweighted over metrics applicable to each trial.",
        "",
        "## Artifacts",
        "",
        f"- Raw: `cogmembench/results/raw/{manifest['run_id']}.jsonl`",
        f"- Evaluated: `cogmembench/results/evaluated/{manifest['run_id']}.jsonl`",
        f"- Trace: `cogmembench/results/traces/{manifest['run_id']}.jsonl`",
        f"- Aggregate: `cogmembench/results/aggregated/{manifest['run_id']}.json`",
        "",
    ]
    return "\n".join(lines)
