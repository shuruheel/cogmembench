from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from cogmembench import cli
from cogmembench.agents import CONDITIONS, CORE_CONDITIONS
from cogmembench.scenarios.schema import load_jsonl


def _parse(*argv: str) -> argparse.Namespace:
    return cli.build_parser().parse_args(list(argv))


def _json_objects(text: str) -> list[dict]:
    """Decode one or more whitespace-separated JSON objects printed to stdout.

    Handlers that call another cmd_* function internally (cmd_run auto-generating
    scenarios via cmd_generate) print more than one JSON document in sequence.
    """
    decoder = json.JSONDecoder()
    text = text.strip()
    objects = []
    index = 0
    while index < len(text):
        obj, end = decoder.raw_decode(text, index)
        objects.append(obj)
        index = end
        while index < len(text) and text[index].isspace():
            index += 1
    return objects


def test_cmd_inspect_reports_json_shape(isolated_root, capsys):
    rc = cli.cmd_inspect(_parse("inspect"))
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["package_root"] == str(isolated_root)
    assert payload["audit"] == str(
        isolated_root / "docs" / "COGNITIVE_SUBSTRATE_IMPLEMENTATION_STATUS.md"
    )
    assert payload["audit_exists"] is False
    assert set(payload["conditions"]) == set(CONDITIONS)
    assert payload["backend_labels"] == ["reference", "mindgraph-local", "mindgraph-cloud"]


def test_cmd_generate_writes_default_scenario_path(isolated_root, capsys):
    rc = cli.cmd_generate(_parse("generate", "--scale", "smoke", "--seed", "42"))
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    expected_path = isolated_root / "scenarios" / "fixtures" / "smoke-42.jsonl"
    assert Path(payload["path"]) == expected_path
    assert payload["seed"] == 42
    assert expected_path.exists()
    lines = [line for line in expected_path.read_text().splitlines() if line.strip()]
    assert payload["scenarios"] == len(lines) > 0
    assert payload["families"] >= 1


def test_cmd_generate_writes_custom_output_path(isolated_root, capsys):
    custom = isolated_root / "custom" / "scenarios.jsonl"
    rc = cli.cmd_generate(
        _parse("generate", "--scale", "smoke", "--seed", "7", "--output", str(custom))
    )
    assert rc == 0
    capsys.readouterr()
    assert custom.exists()
    # the default scenario path must stay untouched when --output is given
    assert not (isolated_root / "scenarios" / "fixtures" / "smoke-7.jsonl").exists()


def test_cmd_generate_rejects_unknown_scale(isolated_root):
    with pytest.raises(SystemExit, match="unknown scale"):
        cli.cmd_generate(_parse("generate", "--scale", "not-a-real-scale"))


def test_cmd_run_auto_generates_scenarios_when_missing(isolated_root, capsys):
    scenario_path = isolated_root / "scenarios" / "fixtures" / "smoke-42.jsonl"
    assert not scenario_path.exists()

    run_id = "pytest-auto-generate"
    rc = cli.cmd_run(
        _parse(
            "run",
            "--scale", "smoke",
            "--seed", "42",
            "--model", "deterministic-v1",
            "--backend", "reference",
            "--run-id", run_id,
        )
    )
    assert rc == 0
    assert scenario_path.exists(), "cmd_run must auto-generate missing scenarios"

    # cmd_run calls cmd_generate internally when the scenario file is missing, so
    # stdout holds the generate summary followed by the run manifest.
    objects = _json_objects(capsys.readouterr().out)
    assert len(objects) == 2
    generate_summary, manifest = objects
    assert Path(generate_summary["path"]) == scenario_path
    assert manifest["run_id"] == run_id
    assert manifest["conditions"] == list(CORE_CONDITIONS)

    raw_path = isolated_root / "results" / "raw" / f"{run_id}.jsonl"
    assert raw_path.exists()
    rows = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()]
    assert len(rows) == manifest["scenario_count"] * len(CORE_CONDITIONS)
    assert all(row["valid"] for row in rows)


def test_cmd_run_uses_explicit_scenarios_without_regenerating(isolated_root, capsys):
    scenario_path = isolated_root / "scenarios" / "explicit.jsonl"
    assert cli.cmd_generate(
        _parse("generate", "--scale", "smoke", "--seed", "42", "--output", str(scenario_path))
    ) == 0
    capsys.readouterr()
    default_path = isolated_root / "scenarios" / "fixtures" / "smoke-42.jsonl"

    rc = cli.cmd_run(
        _parse(
            "run",
            "--scale", "smoke",
            "--seed", "42",
            "--model", "deterministic-v1",
            "--backend", "reference",
            "--scenarios", str(scenario_path),
            "--run-id", "pytest-explicit-scenarios",
        )
    )
    assert rc == 0
    # stdout must hold only the run manifest: no implicit cmd_generate call happened
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["scenario_file"] == str(scenario_path)
    assert not default_path.exists()


def test_full_pipeline_generate_run_evaluate_report_compare(isolated_root, capsys):
    scenario_path = isolated_root / "scenarios" / "pipeline-smoke.jsonl"
    assert cli.cmd_generate(
        _parse(
            "generate",
            "--scale", "smoke",
            "--seed", "42",
            "--output", str(scenario_path),
        )
    ) == 0
    capsys.readouterr()

    run_id = "pytest-pipeline"
    assert cli.cmd_run(
        _parse(
            "run",
            "--scale", "smoke",
            "--seed", "42",
            "--model", "deterministic-v1",
            "--backend", "reference",
            "--scenarios", str(scenario_path),
            "--run-id", run_id,
        )
    ) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["run_id"] == run_id
    assert manifest["scenario_file"] == str(scenario_path)

    # cmd_export against the run the chain just produced, both by explicit id and "latest"
    assert cli.cmd_export(_parse("export-trajectories", "--run-id", run_id)) == 0
    exported = Path(capsys.readouterr().out.strip())
    assert exported == isolated_root / "results" / "trajectories" / f"{run_id}.jsonl"
    assert exported.exists()

    assert cli.cmd_export(_parse("export-trajectories", "--run-id", "latest")) == 0
    exported_latest = Path(capsys.readouterr().out.strip())
    assert exported_latest == exported

    assert cli.cmd_evaluate(_parse("evaluate", "--run-id", run_id)) == 0
    evaluate_summary = json.loads(capsys.readouterr().out)
    assert evaluate_summary["run_id"] == run_id
    assert evaluate_summary["invalid"] == 0
    assert evaluate_summary["evaluated"] == evaluate_summary["trials"]
    evaluated_path = isolated_root / "results" / "evaluated" / f"{run_id}.jsonl"
    assert evaluated_path.exists()

    assert cli.cmd_report(_parse("report", "--run-id", run_id)) == 0
    report_summary = json.loads(capsys.readouterr().out)
    aggregated_path = Path(report_summary["aggregate"])
    assert aggregated_path == isolated_root / "results" / "aggregated" / f"{run_id}.json"
    assert aggregated_path.exists()
    docs_report = isolated_root / "docs" / "RESULTS.md"
    assert Path(report_summary["report"]) == docs_report
    assert docs_report.exists()
    plot_path = Path(report_summary["plot"])
    assert plot_path.exists()
    assert plot_path.suffix == ".svg"

    assert cli.cmd_compare(
        _parse("compare", "--run-ids", run_id, "--output-id", "pytest-pipeline-compare")
    ) == 0
    compare_summary = json.loads(capsys.readouterr().out)
    compare_path = Path(compare_summary["aggregate"])
    assert compare_path.exists()
    compare_payload = json.loads(compare_path.read_text())
    assert compare_payload["run_ids"] == [run_id]
    assert docs_report.read_text() != ""  # compare also rewrote docs/RESULTS.md in place

    # cmd_replay reuses the scenarios already generated above against one condition
    scenarios = load_jsonl(scenario_path)
    scenario_id = scenarios[0].public.scenario_id
    assert cli.cmd_replay(
        _parse(
            "replay",
            "--scenario", scenario_id,
            "--condition", "stateless",
            "--scale", "smoke",
            "--seed", "42",
            "--model", "deterministic-v1",
            "--backend", "reference",
            "--scenarios", str(scenario_path),
        )
    ) == 0
    replay_manifest = json.loads(capsys.readouterr().out)
    assert replay_manifest["run_id"] == f"replay-{scenario_id}-stateless"
    replay_raw = isolated_root / "results" / "raw" / f"{replay_manifest['run_id']}.jsonl"
    assert replay_raw.exists()


def test_cmd_replay_rejects_unknown_scenario(isolated_root, capsys):
    scenario_path = isolated_root / "scenarios" / "fixtures" / "smoke-42.jsonl"
    assert cli.cmd_generate(
        _parse("generate", "--scale", "smoke", "--seed", "42")
    ) == 0
    capsys.readouterr()

    with pytest.raises(SystemExit, match="scenario not found"):
        cli.cmd_replay(
            _parse(
                "replay",
                "--scenario", "does-not-exist",
                "--condition", "stateless",
                "--scale", "smoke",
                "--seed", "42",
                "--scenarios", str(scenario_path),
            )
        )


def test_main_builds_parser_and_dispatches(isolated_root, capsys):
    rc = cli.main(["inspect"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["package_root"] == str(isolated_root)
