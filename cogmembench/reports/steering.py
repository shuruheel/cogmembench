from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any


def build_steering_report(
    rows: list[dict[str, Any]],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate treatment outcomes and localize the largest pipeline deficit."""
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    difficulty_cells: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    capabilities: dict[str, dict[str, Any] | None] = {}
    for row in rows:
        if not row.get("valid", True):
            continue
        metrics = row.get("evaluation", {}).get("metrics", {})
        if "task_success" not in metrics:
            continue
        key = (str(row["family"]), str(row["condition"]))
        cells[key].append(float(metrics["task_success"]))
        difficulty_cells[
            (
                str(row["family"]),
                str(row.get("difficulty_tier", "unspecified")),
                str(row["condition"]),
            )
        ].append(float(metrics["task_success"]))
        capabilities[str(row["condition"])] = row.get("capabilities")

    families: dict[str, Any] = {}
    family_names = sorted({family for family, _ in cells})
    for family in family_names:
        scores = {
            condition: mean(values)
            for (cell_family, condition), values in cells.items()
            if cell_family == family
        }
        oracle = scores.get("oracle-passive")
        automatic = scores.get("automatic-passive")
        active = scores.get("agent-directed-active")
        transcript = scores.get("transcript")
        stateless = scores.get("stateless")
        deltas = {
            "oracle_minus_automatic": oracle - automatic
            if oracle is not None and automatic is not None
            else None,
            "oracle_minus_agent_directed": oracle - active
            if oracle is not None and active is not None
            else None,
            "automatic_minus_transcript": automatic - transcript
            if automatic is not None and transcript is not None
            else None,
            "transcript_minus_stateless": transcript - stateless
            if transcript is not None and stateless is not None
            else None,
        }
        ranked = sorted(
            (
                ("automatic_capture_or_organization", deltas["oracle_minus_automatic"]),
                ("agent_capture_or_tool_policy", deltas["oracle_minus_agent_directed"]),
                ("persistent_retrieval_or_use", deltas["automatic_minus_transcript"]),
                ("longitudinal_context", deltas["transcript_minus_stateless"]),
            ),
            key=lambda item: item[1] if item[1] is not None else float("-inf"),
            reverse=True,
        )
        largest = ranked[0]
        families[family] = {
            "task_success_by_condition": scores,
            "task_success_by_difficulty": {
                tier: {
                    condition: mean(values)
                    for (cell_family, cell_tier, condition), values in difficulty_cells.items()
                    if cell_family == family and cell_tier == tier
                }
                for tier in sorted(
                    {
                        cell_tier
                        for cell_family, cell_tier, _ in difficulty_cells
                        if cell_family == family
                    }
                )
            },
            "treatment_deltas": deltas,
            "primary_localization": (
                {"stage": largest[0], "gap": largest[1]}
                if largest[1] is not None
                else {"stage": "insufficient_cells", "gap": None}
            ),
        }
    report = {
        "schema_version": 1,
        "families": families,
        "capability_manifests_by_condition": capabilities,
        "interpretation": {
            "oracle_minus_automatic": "capture and organization deficit under fixed retrieval",
            "oracle_minus_agent_directed": "agent capture/tool-policy deficit",
            "automatic_minus_transcript": "net value of persistent capture plus retrieval/use",
            "transcript_minus_stateless": "value of budgeted longitudinal context",
        },
    }
    if previous is not None:
        score_changes: dict[str, Any] = {}
        for family, current in families.items():
            old_scores = previous.get("families", {}).get(family, {}).get(
                "task_success_by_condition", {}
            )
            changes = {
                condition: score - float(old_scores[condition])
                for condition, score in current["task_success_by_condition"].items()
                if condition in old_scores
            }
            score_changes[family] = {
                "deltas": changes,
                "improvements": {
                    key: value for key, value in changes.items() if value > 0
                },
                "regressions": {
                    key: value for key, value in changes.items() if value < 0
                },
            }
        old_capabilities = previous.get("capability_manifests_by_condition", {})
        capability_changes = {
            condition: {"previous": old_capabilities.get(condition), "current": manifest}
            for condition, manifest in capabilities.items()
            if old_capabilities.get(condition) != manifest
        }
        report["longitudinal_comparison"] = {
            "score_changes": score_changes,
            "capability_manifest_changes": capability_changes,
        }
    return report


def render_steering_markdown(report: dict[str, Any]) -> str:
    lines = ["# Cognitive-v2 Steering Report", ""]
    for family, result in report["families"].items():
        lines.extend((f"## {family}", "", "| Condition | Task success |", "|---|---:|"))
        for condition, score in sorted(result["task_success_by_condition"].items()):
            lines.append(f"| {condition} | {score:.3f} |")
        localization = result["primary_localization"]
        gap = localization["gap"]
        lines.extend(
            (
                "",
                f"Primary localization: `{localization['stage']}`"
                + (f" (gap {gap:.3f})." if gap is not None else "."),
                "",
            )
        )
        difficulty = result.get("task_success_by_difficulty", {})
        if difficulty:
            lines.extend(("Task success by difficulty:", ""))
            for tier, conditions in difficulty.items():
                rendered = ", ".join(
                    f"{condition}={score:.3f}"
                    for condition, score in sorted(conditions.items())
                )
                lines.append(f"- {tier}: {rendered}")
            lines.append("")
    hierarchical = report.get("hierarchical_analysis")
    if hierarchical:
        lines.extend(("## Hierarchical uncertainty", ""))
        paired = hierarchical["paired_effects_vs_baseline"]
        for condition, summary in paired["effects"].items():
            if summary["mean"] is None:
                continue
            lines.append(
                f"- {condition} vs {paired['baseline_cell']}: "
                f"{summary['mean']:.3f} "
                f"[{summary['ci95_low']:.3f}, {summary['ci95_high']:.3f}] "
                f"across {summary['n_worlds']} worlds."
            )
        for result in hierarchical.get("ablation_effects", {}).values():
            effect = result["effect"]
            if effect["mean"] is None:
                continue
            lines.append(
                f"- {result['feature']} on {result['condition']} (ablated minus full): "
                f"{effect['mean']:.3f} "
                f"[{effect['ci95_low']:.3f}, {effect['ci95_high']:.3f}]."
            )
        lines.append("")
    comparison = report.get("longitudinal_comparison")
    if comparison:
        lines.extend(("## Longitudinal changes", ""))
        for family, changes in comparison["score_changes"].items():
            lines.append(f"- {family}: " + ", ".join(
                f"{condition} {delta:+.3f}"
                for condition, delta in sorted(changes["deltas"].items())
            ))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
