from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_trajectories(run_id: str, root: Path) -> Path:
    trace_path = root / "results" / "traces" / f"{run_id}.jsonl"
    raw_path = root / "results" / "raw" / f"{run_id}.jsonl"
    scores: dict[tuple[str, str], dict[str, Any]] = {}
    with raw_path.open() as fh:
        for line in fh:
            row = json.loads(line)
            scores[(row["scenario_id"], row["condition"])] = row.get("evaluation", {}).get("metrics", {})
    out = root / "results" / "trajectories" / f"{run_id}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open() as src, out.open("w") as dst:
        for line in src:
            event = json.loads(line)
            if event.get("event_type") != "tool_call" or event.get("condition") not in {
                "mindgraph-active-prefetch",
                "mindgraph-active-pull",
                "oracle-policy",
            }:
                continue
            payload = event.get("payload", {})
            args = payload.get("arguments", {})
            metrics = scores.get((event.get("scenario_id", ""), event.get("condition", "")), {})
            row = {
                "scenario_id": event.get("scenario_id"),
                "session_id": event.get("session_id"),
                "turn_id": event.get("turn_id"),
                "condition": event.get("condition"),
                "cognitive_state": {
                    "objective": args.get("summary", ""),
                    "known_facts": [],
                    "active_hypotheses": [],
                    "open_questions": [],
                    "current_decisions": [],
                    "uncertainties": [],
                },
                "available_tools": ["mindgraph_capture", "mindgraph_reason", "mindgraph_commit", "mindgraph_plan", "mindgraph_retrieve"],
                "chosen_action": {"type": "tool_call", "tool": payload.get("tool"), "arguments": args},
                "observation": payload.get("observation", {}),
                "graph_delta": (
                    {}
                    if payload.get("tool") == "mindgraph_retrieve"
                    else payload.get("observation", {})
                ),
                "evaluation": {
                    "useful": None,
                    "primitive_correct": None,
                    "write_quality": None,
                    "annotation_status": "pending_step_review",
                    "trial_metrics": {
                        "task_success": metrics.get("task_success"),
                        "memory_precision": metrics.get("memory_precision"),
                        "correct_primitive_selection": metrics.get(
                            "correct_primitive_selection"
                        ),
                        "harmful_write_rate": metrics.get("harmful_write_rate"),
                    },
                    "notes": (
                        "Observable tool/result trace only; trial-level metrics are context, "
                        "not step labels. No hidden chain-of-thought."
                    ),
                },
            }
            dst.write(json.dumps(row, sort_keys=True) + "\n")
    return out
