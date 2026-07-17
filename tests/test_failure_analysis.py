from cogmembench.reports.failures import build_failure_analysis, classify_failure


def test_failure_taxonomy_separates_timeout_and_pipeline_failures() -> None:
    timeout = classify_failure({"valid": False, "error": "TimeoutError: slow"})
    capture = classify_failure(
        {
            "valid": True,
            "evaluation": {
                "metrics": {"task_success": 0.0, "appropriate_write_rate": 0.0}
            },
        }
    )
    assert timeout["primary"] == "timeout"
    assert capture["primary"] == "capture"


def test_failure_analysis_reports_primary_and_multilabel_counts() -> None:
    rows = [
        {
            "trial_id": "t1",
            "scenario_id": "w1",
            "family": "recursive_investigation",
            "condition": "automatic-passive",
            "valid": True,
            "evaluation": {
                "metrics": {
                    "task_success": 0.0,
                    "appropriate_retrieval_rate": 0.0,
                    "stale_conclusion_intrusion_rate": 1.0,
                }
            },
        },
        {
            "trial_id": "t2",
            "scenario_id": "w2",
            "family": "recursive_investigation",
            "condition": "automatic-passive",
            "valid": True,
            "evaluation": {"metrics": {"task_success": 1.0}},
        },
    ]
    result = build_failure_analysis(rows)
    assert result["primary_counts"] == {"retrieval": 1, "success": 1}
    assert result["flag_counts"]["stale_or_contaminated_memory"] == 1
