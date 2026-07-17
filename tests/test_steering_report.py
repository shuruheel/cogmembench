from __future__ import annotations

from cogmembench.reports import build_steering_report, render_steering_markdown


def test_steering_report_localizes_capture_gap() -> None:
    rows = [
        {
            "family": "recursive_investigation",
            "condition": condition,
            "difficulty_tier": "hard",
            "evaluation": {"metrics": {"task_success": score}},
        }
        for condition, score in (
            ("stateless", 0.0),
            ("transcript", 0.4),
            ("automatic-passive", 0.3),
            ("agent-directed-active", 0.2),
            ("oracle-passive", 1.0),
        )
    ]

    report = build_steering_report(rows)

    family = report["families"]["recursive_investigation"]
    assert family["treatment_deltas"]["oracle_minus_automatic"] == 0.7
    assert family["primary_localization"]["stage"] == "agent_capture_or_tool_policy"
    assert family["task_success_by_difficulty"]["hard"]["oracle-passive"] == 1.0
    assert "recursive_investigation" in render_steering_markdown(report)


def test_steering_report_compares_prior_run() -> None:
    previous = build_steering_report(
        [
            {
                "family": "decision_lineage",
                "condition": "automatic-passive",
                "evaluation": {"metrics": {"task_success": 0.4}},
            }
        ]
    )
    current = build_steering_report(
        [
            {
                "family": "decision_lineage",
                "condition": "automatic-passive",
                "evaluation": {"metrics": {"task_success": 0.7}},
            }
        ],
        previous,
    )

    changes = current["longitudinal_comparison"]["score_changes"]["decision_lineage"]
    assert round(changes["improvements"]["automatic-passive"], 10) == 0.3
