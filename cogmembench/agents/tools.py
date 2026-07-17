from __future__ import annotations

from typing import Any


def _tool(name: str, description: str, actions: list[str], fields: dict[str, Any] | None = None) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "action": {"type": "string", "enum": actions},
        "label": {"type": "string"},
        "summary": {"type": "string"},
    }
    properties.update(fields or {})
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": ["action"]},
        },
    }


ACTIVE_TOOLS = [
    _tool("mindgraph_capture", "Capture entities, observations and preferences.", ["entity", "observation", "preference"]),
    _tool("mindgraph_reason", "Record claims, evidence, questions and hypotheses.", ["claim", "evidence", "open_question", "hypothesis"]),
    _tool("mindgraph_commit", "Track goals, projects and decisions.", ["goal", "project", "open_decision", "resolve_decision"]),
    _tool(
        "mindgraph_plan",
        "Track tasks, execution failures and reusable policies.",
        ["create_task", "update_status", "fail_execution", "create_policy"],
        {"execution_uid": {"type": "string", "description": "Existing execution UID when transitioning an execution to failed."}},
    ),
    _tool("mindgraph_retrieve", "Retrieve persistent graph memory before acting.", ["text", "semantic", "hybrid"], {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}),
]

HERMES_CONTRACT = """You have persistent structured memory. Store durable preferences and
corrections, sourced claims and evidence, goals/decisions/tasks, failures and reusable lessons
without waiting to be asked. Retrieve before recommendations, continuity questions or resumed
work. Keep entity identity separate from observations, preserve provenance and uncertainty,
and do not commit temporary details. Use claims only for falsifiable statements and never
inflate confidence. Do not expose hidden reasoning; return only requested observable output."""
