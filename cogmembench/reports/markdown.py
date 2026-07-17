from __future__ import annotations

from typing import Any


def _v(value: Any, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render_report(aggregate: dict[str, Any], manifest: dict[str, Any]) -> str:
    conditions = aggregate["conditions"]
    evidence_warning = (
        "Reference-backend results validate the harness and are not evidence about MindGraph."
        if manifest["backend"] == "reference"
        else "Actual-backend smoke results are preliminary; confidence intervals are descriptive at this scale."
    )
    lines = [
        "# CogMemBench Results",
        "",
        f"> Auto-generated from raw trial artifacts. {evidence_warning}",
        "",
        "## Run",
        "",
        f"- Run ID: `{manifest['run_id']}`",
        f"- Generated: `{manifest['generated_at']}`",
        f"- Scale: `{manifest['scale']}`; model: `{manifest['model']}`; provider: `{manifest['provider']}`",
        f"- Memory backend: `{manifest['backend']}`; token accounting: `{manifest['token_accounting']}`",
        f"- Scenarios: {manifest['scenario_count']}; completed trials: {manifest.get('completed_trials', 0)}",
        "",
        "## Primary outcomes",
        "",
        "| Condition | n | Task success | Continuity | Belief update | Contradiction | Recovery | Composite |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, data in conditions.items():
        m = data["metrics"]
        lines.append(f"| {name} | {data['n']} | {_v(m.get('task_success', {}).get('mean'))} | {_v(m.get('continuity_accuracy', {}).get('mean'))} | {_v(m.get('belief_update_accuracy', {}).get('mean'))} | {_v(m.get('contradiction_handling', {}).get('mean'))} | {_v(m.get('long_horizon_recovery', {}).get('mean'))} | {_v(data['composite']['mean'])} |")
    lines += ["", "## Memory and retrieval quality", "", "| Condition | Memory precision | Memory recall | Contamination | Supersession | Provenance | Structural | Retrieval P/R |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, data in conditions.items():
        m = data["metrics"]
        lines.append(f"| {name} | {_v(m.get('memory_precision', {}).get('mean'))} | {_v(m.get('memory_recall', {}).get('mean'))} | {_v(m.get('memory_contamination', {}).get('mean'))} | {_v(m.get('supersession_correctness', {}).get('mean'))} | {_v(m.get('provenance_completeness', {}).get('mean'))} | {_v(m.get('structural_quality', {}).get('mean'))} | {_v(m.get('retrieval_precision', {}).get('mean'))} / {_v(m.get('retrieval_recall', {}).get('mean'))} |")
    lines += [
        "",
        "## Efficiency",
        "",
        "| Condition | Input tokens | Output tokens | History/retrieval tokens | Model calls | Memory tools | Model latency ms | Wall seconds | Agent cost USD | Embedding calls/tokens | Embedding cost USD | Measured subtotal USD | Storage growth |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, data in conditions.items():
        e = data["efficiency"]
        history = (e.get("historical_context_tokens", {}).get("mean") or 0) + (e.get("retrieved_context_tokens", {}).get("mean") or 0)
        agent_cost = e.get("estimated_inference_cost_usd", {}).get("mean")
        embedding_calls = e.get("embedding_calls", {}).get("mean")
        embedding_tokens = e.get("embedding_input_tokens", {}).get("mean")
        embedding_cost = e.get("estimated_embedding_cost_usd", {}).get("mean")
        measured_subtotal = (agent_cost or 0) + (embedding_cost or 0)
        embedding_usage = (
            f"{_v(embedding_calls, 1)} / {_v(embedding_tokens, 1)}"
            if name == "flat-hybrid"
            else "n/a"
        )
        embedding_cost_text = _v(embedding_cost, 6) if name == "flat-hybrid" else "n/a"
        lines.append(
            f"| {name} | {_v(e.get('input_tokens', {}).get('mean'), 1)} | "
            f"{_v(e.get('output_tokens', {}).get('mean'), 1)} | {_v(history, 1)} | "
            f"{_v(e.get('model_calls', {}).get('mean'), 1)} | "
            f"{_v(e.get('memory_tool_calls', {}).get('mean'), 1)} | "
            f"{_v(e.get('latency_ms', {}).get('mean'), 1)} | "
            f"{_v(e.get('wall_seconds', {}).get('mean'), 1)} | {_v(agent_cost, 6)} | "
            f"{embedding_usage} | {embedding_cost_text} | {_v(measured_subtotal, 6)} | "
            f"{_v(e.get('memory_storage_growth', {}).get('mean'), 1)} |"
        )
    lines += [
        "",
        "## MindGraph server provider usage",
        "",
        "| Condition | Extraction requests | Extraction input/output tokens | Usage-covered responses | Embedding requests | Embedding items/chars | Output vectors |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, data in conditions.items():
        e = data["efficiency"]
        extraction_requests = e.get("mindgraph_extraction_requests", {}).get("mean")
        if extraction_requests is None:
            continue
        extraction_responses = e.get("mindgraph_extraction_responses", {}).get("mean")
        usage_responses = e.get(
            "mindgraph_extraction_usage_reported_responses", {}
        ).get("mean")
        extraction_tokens = (
            f"{_v(e.get('mindgraph_extraction_input_tokens', {}).get('mean'), 1)} / "
            f"{_v(e.get('mindgraph_extraction_output_tokens', {}).get('mean'), 1)}"
        )
        usage_coverage = f"{_v(usage_responses, 1)} / {_v(extraction_responses, 1)}"
        embedding_inputs = (
            f"{_v(e.get('mindgraph_embedding_input_items', {}).get('mean'), 1)} / "
            f"{_v(e.get('mindgraph_embedding_input_chars', {}).get('mean'), 1)}"
        )
        lines.append(
            f"| {name} | {_v(extraction_requests, 1)} | {extraction_tokens} | "
            f"{usage_coverage} | {_v(e.get('mindgraph_embedding_requests', {}).get('mean'), 1)} | "
            f"{embedding_inputs} | {_v(e.get('mindgraph_embedding_output_vectors', {}).get('mean'), 1)} |"
        )
    lines += ["", "## Paired task-success changes versus stateless", "", "| Condition | Mean delta | Relative change | 95% bootstrap CI | Paired standardized effect |", "|---|---:|---:|---:|---:|"]
    for name, data in aggregate["paired"].items():
        delta = data["task_success_delta_vs_stateless"]
        effect = data["paired_standardized_effect"]
        relative = data.get("task_success_relative_vs_stateless")
        relative_text = "n/a" if relative is None else f"{relative * 100:+.1f}%"
        lines.append(f"| {name} | {_v(delta['mean'])} | {relative_text} | [{_v(delta['ci95_low'])}, {_v(delta['ci95_high'])}] | {_v(effect) if effect not in (float('inf'), float('-inf')) else 'infinite (zero variance)'} |")
    weights = ", ".join(f"{key}={value}" for key, value in aggregate["composite_weights"].items())
    lines += ["", "## Composite weights", "", weights + ". Category scores above remain primary.", "", "## Failure analysis", ""]
    failures = aggregate["failures"]
    if not failures:
        lines.append("No deterministic task failures in this run.")
    else:
        for failure in failures[:30]:
            failed = [key for key, passed in failure["checks"].items() if not passed]
            lines.append(f"- `{failure['scenario_id']}` / `{failure['condition']}`: score {_v(failure['score'])}; failed fields: {', '.join(failed) or 'parse failure'}.")
    lines += ["", "## Interpretation and limitations", ""]
    if manifest["backend"] == "reference":
        lines.append("This run used the reference backend and deterministic provider. It demonstrates condition isolation, scoring, tracing and reporting only. It does **not** measure MindGraph or a language model.")
    else:
        lines.append("This run used an actual MindGraph endpoint. Causal interpretation remains limited to the pinned model, integration policy, scenarios and provider configuration recorded in the manifest.")
    lines.append("Reasoning-token values are unavailable when the provider does not expose them. Database-only latency is unavailable over the current HTTP API. The measured subtotal includes tested-agent inference and harness-side flat-hybrid embeddings. MindGraph extraction request and provider-reported token counts are shown separately, but their cost is unavailable without a pinned server-side price table. Server-side embedding requests, input items/characters, and output vectors are reported; embedding tokens and cost remain unavailable because the current provider trait discards usage metadata. Wall time includes extraction. See `LIMITATIONS.md`.")
    lines += [
        "",
        "## Artifacts",
        "",
        f"- Raw trials: `cogmembench/results/raw/{manifest['run_id']}.jsonl`",
        f"- Deterministically evaluated trials: `cogmembench/results/evaluated/{manifest['run_id']}.jsonl`",
        f"- Execution/retrieval traces: `cogmembench/results/traces/{manifest['run_id']}.jsonl`",
        f"- Cognitive trajectories: `cogmembench/results/trajectories/{manifest['run_id']}.jsonl`",
        f"- Comparison plot: `cogmembench/results/plots/{manifest['run_id']}-task-success.svg`",
        "",
        "These artifacts are the source for representative trace and graph-quality audits; the report does not quote a trace that is absent from the raw files.",
    ]
    lines += ["", "## Reproduction", "", "```bash", f"cogmembench generate --scale {manifest['scale']} --seed {manifest['base_seed']}", f"cogmembench run --scale {manifest['scale']} --model {manifest['model']} --conditions {','.join(manifest['conditions'])} --backend {manifest['backend']}", f"cogmembench report --run-id {manifest['run_id']}", "```", ""]
    return "\n".join(lines)
