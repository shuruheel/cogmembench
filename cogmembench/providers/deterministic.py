from __future__ import annotations

import json
import re
from typing import Any

from ..telemetry.tokens import count_messages, count_tokens
from .base import ProviderResponse, ToolCall


class DeterministicProvider:
    """Observable rule model for CI. It is not used as evidence of agent capability."""

    model_id = "deterministic-v1"

    def __init__(self):
        self.calls = 0

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0,
        max_output_tokens: int = 1024,
    ) -> ProviderResponse:
        self.calls += 1
        text = "\n".join(str(m.get("content", "")) for m in messages)
        last = str(messages[-1].get("content", "")) if messages else ""
        tool_names = {t["function"]["name"] for t in (tools or [])}
        calls: list[ToolCall] = []
        if tools and messages and messages[-1].get("role") != "tool":
            calls = self._choose_tools(text, last, tool_names)
        content = "" if calls else self._answer(text, last)
        return ProviderResponse(
            content=content,
            tool_calls=calls,
            input_tokens=count_messages(messages),
            output_tokens=count_tokens(content) + sum(count_tokens(json.dumps(c.arguments)) for c in calls),
            reasoning_tokens=None,
            model=self.model_id,
        )

    def _choose_tools(self, context: str, last: str, names: set[str]) -> list[ToolCall]:
        low = last.lower()
        if "substrate_retrieve" in names and any(
            phrase in low
            for phrase in (
                "return json",
                "return only json",
                "derive and store",
                "reuse the stored",
                "repair and store",
                "reuse the revised",
                "audit the decision",
                "time travel",
                "after the correction",
            )
        ):
            valid = re.search(r"valid time\s+(\d+)", last, re.I)
            known = re.search(r"knowledge available at time\s+(\d+)", last, re.I)
            args: dict[str, Any] = {
                "query": last,
                "max_items": 8,
                "max_context_tokens": 100 if "read budget" in low else 1200,
            }
            if valid:
                args["valid_at"] = int(valid.group(1))
            if known:
                args["known_at"] = int(known.group(1))
            return [ToolCall(f"det-{self.calls}-sr", "substrate_retrieve", args)]
        if "substrate_record" in names and last.strip():
            kind = "observation"
            if low.startswith("decision:"):
                kind = "decision"
            elif low.startswith("executed"):
                kind = "action"
            elif low.startswith("outcome:"):
                kind = "outcome"
            elif "constraint:" in low:
                kind = "constraint"
            elif any(term in low for term in ("reports", "inspection", "diagnostic shard")):
                kind = "evidence"
            return [
                ToolCall(
                    f"det-{self.calls}-sw",
                    "substrate_record",
                    {
                        "artifact_id": f"agent:{self.calls}",
                        "kind": kind,
                        "content": last,
                        "valid_start": 0,
                        "status": "accepted",
                        "provenance_event_ids": [],
                    },
                )
            ]
        if "return only json" in low and "mindgraph_retrieve" in names:
            return [ToolCall(f"det-{self.calls}-r", "mindgraph_retrieve", {"query": last, "action": "hybrid", "limit": 5})]
        if ("prefer" in low or "avoid" in low or "correction:" in low) and "mindgraph_capture" in names:
            return [ToolCall(f"det-{self.calls}-p", "mindgraph_capture", {"action": "preference", "label": last[:100], "summary": last})]
        if any(k in low for k in ("source alpha", "authoritative", "retracted")) and "mindgraph_reason" in names:
            return [ToolCall(f"det-{self.calls}-c", "mindgraph_reason", {"action": "claim", "label": last[:100], "summary": last})]
        if any(k in low for k in ("project ", "decision:")) and "mindgraph_commit" in names:
            action = "open_decision" if "decision:" in low else "project"
            return [ToolCall(f"det-{self.calls}-g", "mindgraph_commit", {"action": action, "label": last[:100], "summary": last})]
        if any(k in low for k in ("completed", "failed", "lesson applies")) and "mindgraph_plan" in names:
            action = "fail_execution" if "failed" in low else "create_policy"
            return [ToolCall(f"det-{self.calls}-x", "mindgraph_plan", {"action": action, "label": last[:100], "summary": last})]
        return []

    def _answer(self, context: str, last: str) -> str:
        # A tool result is the last message in active mode, so task detection must
        # consider the full observable conversation rather than only the last item.
        low = context.lower()
        latest_repair = context.lower().rfind("after the correction")
        latest_history = context.lower().rfind("time travel:")
        latest_current = context.lower().rfind("at valid time")
        if max(latest_repair, latest_history, latest_current) >= 0:
            old = re.findall(r"reports .+? as (.+?) for (.+?), effective", context, re.I)
            new = re.findall(r"has been (.+?) for (.+?) since logical time", context, re.I)
            if latest_repair > max(latest_history, latest_current):
                decision = re.findall(
                    r"Decision based on that report:\s*(.+?)\. Independent constraint:",
                    context,
                    re.I,
                )
                constraint = re.findall(r"Independent constraint:\s*(.+?)\.", context, re.I)
                return json.dumps(
                    {
                        "invalidated": decision[-1] if decision else "unknown",
                        "preserved": constraint[-1] if constraint else "unknown",
                        "confidence": 1.0,
                    }
                )
            historical = latest_history >= 0 and (
                latest_history > latest_current or latest_current - latest_history < 40
            )
            chosen = old[-1] if historical and old else (new[-1] if new else (old[-1] if old else None))
            return json.dumps(
                {
                    "value": chosen[0] if chosen else "unknown",
                    "scope": chosen[1] if chosen else "unknown",
                    "knowledge_state": "provisional" if historical and old else (
                        "corrected" if new else "unknown"
                    ),
                    "confidence": 1.0,
                }
            )
        latest_recursive = max(
            context.lower().rfind("derive and store the incident conclusion"),
            context.lower().rfind("reuse the stored conclusion"),
            context.lower().rfind("repair and store the incident conclusion"),
            context.lower().rfind("reuse the revised conclusion"),
        )
        if latest_recursive >= 0:
            root = re.findall(r"Inspection of ([a-z0-9_-]+):", context, re.I)
            corrected_root = re.findall(
                r"Replacement inspection of ([a-z0-9_-]+):", context, re.I
            )
            initial_cause = re.findall(
                r"failure signature is consistent with (.+?)\.", context, re.I
            )
            corrected_cause = re.findall(
                r"corrected failure signature is (.+?);", context, re.I
            )
            remediation = re.findall(
                r"remediation catalog maps this signature to (.+?)\.", context, re.I
            )
            corrected_remediation = re.findall(
                r"remediation catalog now maps it to (.+?)\.", context, re.I
            )
            if corrected_root:
                root = corrected_root
            cause = corrected_cause or initial_cause
            if corrected_remediation:
                remediation = corrected_remediation
            if not root:
                root = re.findall(r'"root_service"\s*:\s*"([^"]+)"', context, re.I)
            if not cause:
                cause = re.findall(r'"root_cause"\s*:\s*"([^"]+)"', context, re.I)
            if not remediation:
                remediation = re.findall(r'"remediation"\s*:\s*"([^"]+)"', context, re.I)
            answer = {
                "root_service": root[-1] if root else "unknown",
                "root_cause": cause[-1] if cause else "unknown",
                "remediation": remediation[-1] if remediation else "unknown",
                "confidence": 1.0,
            }
            if "reuse the stored conclusion" in context.lower()[latest_recursive:]:
                answer["basis"] = "stored conclusion" if all(
                    answer[key] != "unknown"
                    for key in ("root_service", "root_cause", "remediation")
                ) else "unknown"
            if "repair and store the incident conclusion" in context.lower()[latest_recursive:]:
                answer["superseded_conclusion"] = (
                    initial_cause[-1] if initial_cause else "unknown"
                )
            if "reuse the revised conclusion" in context.lower()[latest_recursive:]:
                answer["basis"] = "revised conclusion" if all(
                    answer[key] != "unknown"
                    for key in ("root_service", "root_cause", "remediation")
                ) else "unknown"
            return json.dumps(answer)
        if "audit the decision using only its contemporaneous evidence" in low:
            signal = re.findall(r"reports (.+?)\.", context, re.I)
            constraint = re.findall(r"Decision constraint:\s*(.+?)\. Alternatives", context, re.I)
            decision = re.findall(r"Decision:\s*(.+?)\.", context, re.I)
            action = re.findall(r"Executed (.+?)\.", context, re.I)
            outcome = re.findall(r"Outcome:\s*(.+?)\.", context, re.I)
            return json.dumps(
                {
                    "evidence": signal[-1] if signal else "unknown",
                    "constraint": constraint[-1] if constraint else "unknown",
                    "decision": decision[-1] if decision else "unknown",
                    "action": action[-1] if action else "unknown",
                    "outcome": outcome[-1] if outcome else "unknown",
                    "later_evidence_excluded": True,
                    "confidence": 1.0,
                }
            )
        if "keys choice, avoid, basis" in low:
            corrections = re.findall(r"now prefers ([^.]+?) instead of ([^.]+?) for regional", context, re.I)
            base = re.findall(r"regional trips, prefer ([^.]+?)\.", context, re.I)
            avoid = re.findall(r"always avoid ([^.]+?)\.", context, re.I)
            choice = corrections[-1][0] if corrections else (base[-1] if base else "unknown")
            return json.dumps({"choice": choice, "avoid": avoid[-1] if avoid else "unknown", "basis": "corrected preference" if corrections else "available context"})
        if "launch_date" in low and "old_claim_status" in low:
            beta = re.findall(r"Beta says .*?US on (March \d+)", context, re.I)
            alpha = re.findall(r"Alpha says .*?US on (March \d+)", context, re.I)
            return json.dumps({"launch_date": beta[-1] if beta else (alpha[-1] if alpha else "unknown"), "region": "US" if (beta or alpha) else "unknown", "old_claim_status": "retracted" if "retracted" in context.lower() else "unknown", "evidence": "Beta" if beta else ("Alpha" if alpha else "unknown"), "europe_status": "unknown"})
        if "next_action" in low and "avoid_repeat" in low:
            schema = re.findall(r"validate against (schema-v\d+)", context, re.I)
            return json.dumps({"completed": "design mapping" if "mapping completed" in context.lower() else "unknown", "failed": "parser" if "parser attempt failed" in context.lower() else "unknown", "next_action": f"validate against {schema[-1]}" if schema else "unknown", "decision": "streaming parsing" if "streaming parsing" in context.lower() else "unknown", "avoid_repeat": "parse without schema" if "lacked a declared schema" in context.lower() else "unknown"})
        if "similar_method" in low and "control_method" in low:
            available = re.findall(r"A robust (.+?) parser is available", context, re.I)
            return json.dumps({"similar_method": available[-1] if available else "unknown", "control_method": "fixed-width binary decoder", "failure_cause": "quoted delimiter" if "quoted fields" in context.lower() else "unknown", "scope": "delimited text only" if "applies to delimited text" in context.lower() else "unknown"})
        return json.dumps({"acknowledged": True})
