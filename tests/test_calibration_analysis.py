from cogmembench.reports.calibration import build_calibration_analysis


def test_calibration_analysis_reports_ece_and_missingness() -> None:
    rows = [
        {"evaluation": {"metrics": {"confidence_mean": 0.9, "task_success": 1.0}}},
        {"evaluation": {"metrics": {"confidence_mean": 0.8, "task_success": 0.0}}},
        {"evaluation": {"metrics": {"confidence_mean": None, "task_success": 1.0}}},
    ]
    result = build_calibration_analysis(rows, bins=5)
    assert result["observations"] == 2
    assert result["expected_calibration_error"] is not None
    assert result["missing_confidence_rows"] == 1
