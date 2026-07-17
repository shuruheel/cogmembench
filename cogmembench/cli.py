from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from .agents import CONDITIONS, CORE_CONDITIONS
from .config import ROOT, load_config
from .evaluators import evaluate_trial, evaluate_trial_v2
from .memory import OpenAIEmbeddingProvider
from .reports import (
    aggregate_results,
    build_calibration_analysis,
    build_hierarchical_analysis,
    build_power_analysis,
    build_run_cost_model,
    build_failure_analysis,
    build_steering_report,
    compare_repetitions,
    load_evaluated_runs,
    render_development_v2_report,
    render_repetition_report,
    render_report,
    render_steering_markdown,
)
from .reports.plots import write_task_success_svg
from .protocol_v2 import freeze_protocol, verify_protocol_freeze
from .runners import BenchmarkRunner, CognitiveV2Runner
from .scenarios.generators import (
    generate_bitemporal_belief_revision,
    generate_decision_lineage,
    generate_development_v2,
    generate_recursive_investigation,
    generate_suite,
)
from .scenarios.schema import load_jsonl, save_jsonl
from .scenarios.release import prepare_release
from .scenarios.realization import apply_publication_holdout_v1
from .substrate import (
    DeterministicHashEmbeddingProvider,
    AblationFeature,
    CogneeRecordStore,
    FlatSubstrateAdapter,
    HybridSubstrateAdapter,
    MappedJournalSubstrateAdapter,
    Mem0OSSRecordStore,
    MindGraphRecordStore,
    ReferenceSubstrateAdapter,
    SummarySubstrateAdapter,
    VectorSubstrateAdapter,
    ZepCloudRecordStore,
)
from .substrate.conditions import COGNITIVE_V2_CONDITIONS
from .trajectory import export_trajectories
from .validation import (
    audit_adapter_portability,
    build_blinded_annotation_packet,
    score_human_agreement,
    validate_adapter_contract,
    validate_cognitive_v2_scenarios,
    validate_counterfactual_oracles,
    validate_evaluator_adversarial_corpus,
    validate_generator_validity,
)


def _latest(run_id: str) -> str:
    if run_id == "latest":
        path = ROOT / "results" / "LATEST"
        if not path.exists():
            raise SystemExit("no latest run")
        return path.read_text().strip()
    return run_id


def _protocol_metadata(manifest: dict) -> dict:
    value = manifest.get("protocol_lock")
    return value if isinstance(value, dict) else {}


def _scenario_path(scale: str, seed: int) -> Path:
    folder = "held_out" if scale == "publication" else "fixtures"
    return ROOT / "scenarios" / folder / f"{scale}-{seed}.jsonl"


def cmd_inspect(_: argparse.Namespace) -> int:
    audit = ROOT / "docs" / "COGNITIVE_SUBSTRATE_IMPLEMENTATION_STATUS.md"
    print(
        json.dumps(
            {
                "package_root": str(ROOT),
                "audit": str(audit),
                "audit_exists": audit.exists(),
                "conditions": CONDITIONS,
                "backend_labels": ["reference", "mindgraph-local", "mindgraph-cloud"],
            },
            indent=2,
        )
    )
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    generator_version = getattr(args, "generator_version", None)
    if generator_version == "cognitive-v2":
        cognitive_config = load_config("cognitive_v2.yaml")
        profiles = cognitive_config["profiles"]
        if args.scale not in profiles:
            raise SystemExit(
                f"unknown cognitive-v2 profile {args.scale}; choose from "
                f"{', '.join(sorted(profiles))}"
            )
        config = profiles[args.scale]
        generator_seeds = [args.seed]
    else:
        scales = load_config("scales.yaml")
        if args.scale not in scales:
            raise SystemExit(f"unknown scale {args.scale}")
        config = scales[args.scale]
        generator_seeds = (
            [int(item) for item in args.generator_seeds.split(",") if item.strip()]
            if getattr(args, "generator_seeds", None)
            else list(config["seeds"])
        )
    if generator_version == "development-v2":
        if args.scale != "development":
            raise SystemExit("development-v2 generator requires --scale development")
        scenarios = generate_development_v2(
            args.seed,
            int(config["max_agent_steps"]),
            int(getattr(args, "v2_variants", None) or 10),
        )
    elif generator_version == "cognitive-v2":
        variants = int(
            getattr(args, "v2_variants", None) or config["variants_per_family"]
        )
        family = getattr(args, "family", "all") or "all"
        scenarios = []
        if family in {"all", "bitemporal_belief_revision"}:
            scenarios.extend(
                generate_bitemporal_belief_revision(
                    args.seed, int(config["max_agent_steps"]), variants
                )
            )
        if family in {"all", "recursive_investigation"}:
            scenarios.extend(
                generate_recursive_investigation(
                    args.seed, int(config["max_agent_steps"]), variants
                )
            )
        if family in {"all", "decision_lineage"}:
            scenarios.extend(
                generate_decision_lineage(args.seed, int(config["max_agent_steps"]), variants)
            )
    else:
        scenarios = generate_suite(
            args.scale,
            args.seed,
            int(config["variants_per_family"]),
            generator_seeds,
            int(config["max_agent_steps"]),
        )
    if generator_version == "cognitive-v2" and args.scale == "publication":
        scenarios = [apply_publication_holdout_v1(scenario) for scenario in scenarios]
    path = Path(args.output) if args.output else _scenario_path(args.scale, args.seed)
    save_jsonl(path, scenarios)
    print(
        json.dumps(
            {
                "path": str(path),
                "scenarios": len(scenarios),
                "families": len({scenario.public.family for scenario in scenarios}),
                "seed": args.seed,
            },
            indent=2,
        )
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    path = Path(args.scenarios) if args.scenarios else _scenario_path(args.scale, args.seed)
    if not path.exists():
        cmd_generate(argparse.Namespace(scale=args.scale, seed=args.seed, output=str(path)))
    conditions = [item.strip() for item in args.conditions.split(",") if item.strip()]
    runner = BenchmarkRunner(
        scale=args.scale,
        model=args.model,
        conditions=conditions,
        backend=args.backend,
        base_seed=args.seed,
        provider_base_url=args.provider_base_url,
        resume=args.resume,
        run_id=args.run_id,
        protocol_lock=args.protocol_lock,
    )
    manifest = runner.run(path)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def _load_run(run_id: str, *, prefer_evaluated: bool = True) -> tuple[list[dict], dict]:
    run_id = _latest(run_id)
    raw = ROOT / "results" / "raw" / f"{run_id}.jsonl"
    manifest = ROOT / "results" / "raw" / f"{run_id}.manifest.json"
    evaluated = ROOT / "results" / "evaluated" / f"{run_id}.jsonl"
    source = evaluated if prefer_evaluated and evaluated.exists() else raw
    loaded = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    by_trial: dict[str, dict] = {}
    without_trial: list[dict] = []
    for row in loaded:
        if row.get("trial_id"):
            by_trial[row["trial_id"]] = row
        else:
            without_trial.append(row)
    rows = without_trial + list(by_trial.values())
    return rows, json.loads(manifest.read_text())


def cmd_evaluate(args: argparse.Namespace) -> int:
    # Evaluation must always rebuild from the append-only raw log. A resumed run
    # can append successful retries after an evaluated artifact was generated;
    # reading that stale artifact would preserve the superseded failure rows.
    rows, manifest = _load_run(args.run_id, prefer_evaluated=False)
    scenarios = {
        scenario.public.scenario_id: scenario
        for scenario in load_jsonl(Path(manifest["scenario_file"]))
    }
    trace_path = ROOT / "results" / "traces" / f"{manifest['run_id']}.jsonl"
    trace_segments: dict[tuple[str, str], list[list[SimpleNamespace]]] = {}
    current_segment: list[SimpleNamespace] | None = None
    current_key: tuple[str, str] | None = None
    if trace_path.exists():
        for line in trace_path.read_text().splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            event = SimpleNamespace(**data)
            if event.event_type == "model_call" and event.scenario_id:
                key = (event.scenario_id, event.condition)
                if key != current_key:
                    current_key = key
                    current_segment = []
                    trace_segments.setdefault(key, []).append(current_segment)
            if current_segment is not None:
                current_segment.append(event)
    for row in rows:
        if not row.get("valid") or row["scenario_id"] not in scenarios:
            continue
        segments = trace_segments.get((row["scenario_id"], row["condition"]), [[]])
        evaluator = (
            evaluate_trial_v2
            if _protocol_metadata(manifest).get("evaluator_version") == "development-v2"
            else evaluate_trial
        )
        row["evaluation"] = evaluator(
            row,
            scenarios[row["scenario_id"]],
            segments[-1],
        )
    evaluated_path = ROOT / "results" / "evaluated" / f"{manifest['run_id']}.jsonl"
    evaluated_path.parent.mkdir(parents=True, exist_ok=True)
    evaluated_path.write_text(
        "".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in rows)
    )
    invalid = [row for row in rows if not row.get("valid") or not row.get("evaluation")]
    print(
        json.dumps(
            {
                "run_id": manifest["run_id"],
                "trials": len(rows),
                "evaluated": len(rows) - len(invalid),
                "invalid": len(invalid),
                "artifact": str(evaluated_path),
            },
            indent=2,
        )
    )
    return 1 if invalid else 0


def cmd_report(args: argparse.Namespace) -> int:
    rows, manifest = _load_run(args.run_id)
    rows = [row for row in rows if row.get("valid") and row.get("evaluation", {}).get("metrics")]
    weights = load_config("metrics.yaml")["composite"]
    aggregate = aggregate_results(rows, weights)
    out_json = ROOT / "results" / "aggregated" / f"{manifest['run_id']}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(aggregate, indent=2, sort_keys=True, allow_nan=False))
    report_path = ROOT / "docs" / "RESULTS.md"
    report_path.write_text(
        render_development_v2_report(aggregate, manifest)
        if _protocol_metadata(manifest).get("evaluator_version") == "development-v2"
        else render_report(aggregate, manifest)
    )
    plot = write_task_success_svg(
        aggregate, ROOT / "results" / "plots" / f"{manifest['run_id']}-task-success.svg"
    )
    print(
        json.dumps(
            {"aggregate": str(out_json), "report": str(report_path), "plot": str(plot)}, indent=2
        )
    )
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    run_ids = [item.strip() for item in args.run_ids.split(",") if item.strip()]
    runs = load_evaluated_runs(ROOT, run_ids)
    comparison = compare_repetitions(runs, load_config("metrics.yaml")["composite"])
    out_json = ROOT / "results" / "aggregated" / f"{args.output_id}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(comparison, indent=2, sort_keys=True, allow_nan=False))
    report_path = ROOT / "docs" / "RESULTS.md"
    report_path.write_text(render_repetition_report(comparison))
    print(json.dumps({"aggregate": str(out_json), "report": str(report_path)}, indent=2))
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    scenarios = load_jsonl(
        Path(args.scenarios) if args.scenarios else _scenario_path(args.scale, args.seed)
    )
    chosen = [scenario for scenario in scenarios if scenario.public.scenario_id == args.scenario]
    if not chosen:
        raise SystemExit(f"scenario not found: {args.scenario}")
    temp = ROOT / "results" / "raw" / f"replay-{args.scenario}.jsonl"
    save_jsonl(temp, chosen)
    runner = BenchmarkRunner(
        scale=args.scale,
        model=args.model,
        conditions=[args.condition],
        backend=args.backend,
        base_seed=args.seed,
        run_id=f"replay-{args.scenario}-{args.condition}",
    )
    print(json.dumps(runner.run(temp), indent=2))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    path = export_trajectories(_latest(args.run_id), ROOT)
    print(path)
    return 0


def cmd_validate_cognitive_v2(args: argparse.Namespace) -> int:
    scenarios = load_jsonl(Path(args.scenarios))
    result = validate_cognitive_v2_scenarios(scenarios)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        result["artifact"] = str(output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


def cmd_validate_generators_v2(args: argparse.Namespace) -> int:
    result = validate_generator_validity(
        load_jsonl(Path(args.scenarios)),
        min_scenarios_per_family=args.min_scenarios_per_family,
        min_templates_per_family=args.min_templates_per_family,
        min_worlds_per_family=args.min_worlds_per_family,
        min_difficulty_tiers_per_family=getattr(
            args, "min_difficulty_tiers_per_family", 3
        ),
        min_unique_world_ratio=args.min_unique_world_ratio,
        max_template_share=args.max_template_share,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


def cmd_validate_evaluators_v2(args: argparse.Namespace) -> int:
    result = validate_evaluator_adversarial_corpus()
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


def cmd_validate_counterfactuals_v2(args: argparse.Namespace) -> int:
    result = validate_counterfactual_oracles(load_jsonl(Path(args.scenarios)))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


def cmd_validate_adapter_v2(args: argparse.Namespace) -> int:
    base_url = getattr(args, "base_url", None)
    if args.adapter == "reference":
        adapter = ReferenceSubstrateAdapter()
    elif args.adapter == "flat":
        adapter = FlatSubstrateAdapter()
    elif args.adapter == "summary":
        adapter = SummarySubstrateAdapter()
    elif args.adapter in {"vector", "hybrid"}:
        provider_name = getattr(args, "embedding_provider", "deterministic")
        if provider_name == "openai":
            api_key = os.getenv("COGMEMBENCH_EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise SystemExit(
                    "OpenAI embedding validation requires COGMEMBENCH_EMBEDDING_API_KEY "
                    "or OPENAI_API_KEY"
                )
            embedding_provider = OpenAIEmbeddingProvider(
                api_key,
                model=os.getenv("COGMEMBENCH_EMBEDDING_MODEL", "text-embedding-3-small"),
                base_url=os.getenv(
                    "COGMEMBENCH_EMBEDDING_BASE_URL",
                    "https://api.openai.com/v1",
                ),
            )
        else:
            embedding_provider = DeterministicHashEmbeddingProvider()
        adapter = (
            VectorSubstrateAdapter(embedding_provider)
            if args.adapter == "vector"
            else HybridSubstrateAdapter(embedding_provider)
        )
    elif args.adapter == "mindgraph-v2":
        adapter = MappedJournalSubstrateAdapter(
            MindGraphRecordStore(
                base_url or os.getenv("MINDGRAPH_BASE_URL", "http://127.0.0.1:18790"),
                api_key=os.getenv("MINDGRAPH_API_KEY"),
            )
        )
    elif args.adapter == "mem0-oss":
        adapter = MappedJournalSubstrateAdapter(
            Mem0OSSRecordStore(
                base_url or os.getenv("MEM0_BASE_URL", "http://127.0.0.1:8000"),
                api_key=os.getenv("MEM0_API_KEY"),
            )
        )
    elif args.adapter == "cognee":
        adapter = MappedJournalSubstrateAdapter(
            CogneeRecordStore(
                base_url or os.getenv("COGNEE_BASE_URL", "http://127.0.0.1:8000"),
                api_key=os.getenv("COGNEE_API_KEY"),
            )
        )
    else:
        api_key = os.getenv("ZEP_API_KEY")
        if not api_key:
            raise SystemExit("zep-cloud validation requires ZEP_API_KEY")
        adapter = MappedJournalSubstrateAdapter(
            ZepCloudRecordStore(
                api_key,
                base_url=base_url or os.getenv("ZEP_API_URL", "https://api.getzep.com"),
            )
        )
    result = (
        audit_adapter_portability(adapter)
        if getattr(args, "portability_audit", False)
        else validate_adapter_contract(adapter)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


def cmd_run_cognitive_v2(args: argparse.Namespace) -> int:
    conditions = [item.strip() for item in args.conditions.split(",") if item.strip()]
    runner = CognitiveV2Runner(
        model=args.model,
        conditions=conditions,
        adapter=args.adapter,
        base_seed=args.seed,
        run_id=args.run_id,
        results_root=Path(args.results_root) if args.results_root else None,
        provider_base_url=args.provider_base_url,
        retrieval_k=args.retrieval_k,
        retrieval_tokens=args.retrieval_tokens,
        operating_mode=args.operating_mode,
        scaffold_version=args.scaffold,
        ablation=getattr(args, "ablation", None),
    )
    manifest = runner.run(Path(args.scenarios))
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 1 if manifest["invalid_trials"] else 0


def cmd_report_cognitive_v2(args: argparse.Namespace) -> int:
    results_root = Path(args.results_root) if args.results_root else ROOT / "results"
    run_id = _latest(args.run_id)
    evaluated = results_root / "evaluated" / f"{run_id}.jsonl"
    if not evaluated.exists():
        raise SystemExit(f"evaluated cognitive-v2 run not found: {evaluated}")
    rows = [json.loads(line) for line in evaluated.read_text().splitlines() if line.strip()]
    previous = None
    if args.previous_run_id:
        previous_path = (
            results_root / "aggregated" / f"{_latest(args.previous_run_id)}-steering.json"
        )
        if not previous_path.exists():
            raise SystemExit(f"previous steering report not found: {previous_path}")
        previous = json.loads(previous_path.read_text())
    report = build_steering_report(rows, previous)
    report["hierarchical_analysis"] = build_hierarchical_analysis(
        rows,
        metric=getattr(args, "metric", "task_success"),
        iterations=getattr(args, "bootstrap_iterations", 2000),
        seed=getattr(args, "bootstrap_seed", 1729),
    )
    output_json = results_root / "aggregated" / f"{run_id}-steering.json"
    output_markdown = results_root / "aggregated" / f"{run_id}-steering.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    output_markdown.write_text(render_steering_markdown(report))
    print(
        json.dumps(
            {"steering_json": str(output_json), "steering_markdown": str(output_markdown)},
            indent=2,
        )
    )
    return 0


def cmd_analyze_cognitive_v2(args: argparse.Namespace) -> int:
    paths = [Path(value.strip()) for value in args.evaluated.split(",") if value.strip()]
    rows = [
        json.loads(line)
        for path in paths
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    result = build_hierarchical_analysis(
        rows,
        metric=args.metric,
        baseline_cell=args.baseline_cell,
        iterations=args.bootstrap_iterations,
        seed=args.bootstrap_seed,
    )
    result["calibration"] = build_calibration_analysis(
        rows, bins=getattr(args, "calibration_bins", 10)
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _load_evaluated_paths(value: str) -> list[dict]:
    return [
        json.loads(line)
        for path in (Path(item.strip()) for item in value.split(",") if item.strip())
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def cmd_cost_cognitive_v2(args: argparse.Namespace) -> int:
    config = load_config("cognitive_v2_costs.yaml")
    profiles = config["profiles"]
    if args.profile not in profiles:
        raise SystemExit(f"unknown cost profile: {args.profile}")
    result = build_run_cost_model(
        _load_evaluated_paths(args.evaluated),
        profiles[args.profile],
        profile_name=args.profile,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_power_cognitive_v2(args: argparse.Namespace) -> int:
    result = build_power_analysis(
        _load_evaluated_paths(args.evaluated),
        metric=args.metric,
        treatment=args.treatment,
        baseline=args.baseline,
        minimum_effect=args.minimum_effect,
        alpha=args.alpha,
        target_power=args.target_power,
        comparisons=args.comparisons,
        tier_field=args.tier_field,
        assumed_sd=args.assumed_sd,
        frozen_pilot=args.frozen_pilot,
        minimum_pilot_pairs=args.minimum_pilot_pairs,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["publication_ready"] or not args.frozen_pilot else 1


def cmd_failures_cognitive_v2(args: argparse.Namespace) -> int:
    result = build_failure_analysis(_load_evaluated_paths(args.evaluated))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_prepare_release_v2(args: argparse.Namespace) -> int:
    references = {}
    for value in args.reference or []:
        if "=" not in value:
            raise SystemExit("--reference must be NAME=PATH")
        name, path = value.split("=", 1)
        references[name] = load_jsonl(Path(path))
    result = prepare_release(
        load_jsonl(Path(args.scenarios)),
        Path(args.output),
        split=args.split,
        references=references,
        canary_guid=args.canary_guid,
        ngram_size=args.ngram_size,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_freeze_protocol_v2(args: argparse.Namespace) -> int:
    if args.verify:
        result = verify_protocol_freeze(Path(args.verify), root=ROOT)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["passed"] else 1
    if not args.spec or not args.output:
        raise SystemExit("--spec and --output are required when creating a freeze")
    spec = json.loads(Path(args.spec).read_text())
    result = freeze_protocol(
        Path(args.output),
        root=ROOT,
        protocol_id=spec["protocol_id"],
        scenario_file=Path(spec["scenario_file"]),
        frozen_files=[Path(value) for value in spec["frozen_files"]],
        models=[str(value) for value in spec["models"]],
        conditions=[str(value) for value in spec["conditions"]],
        primary_endpoints=spec["primary_endpoints"],
        exclusion_rules=spec["exclusion_rules"],
        analysis_plan=spec["analysis_plan"],
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_export_annotations_v2(args: argparse.Namespace) -> int:
    packet, key = build_blinded_annotation_packet(
        load_jsonl(Path(args.scenarios)), sample_size=args.sample_size, seed=args.seed
    )
    packet_path = Path(args.output)
    key_path = Path(args.answer_key)
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    key_path.write_text(json.dumps(key, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"packet": str(packet_path), "answer_key": str(key_path)}, indent=2))
    return 0


def cmd_agreement_v2(args: argparse.Namespace) -> int:
    annotations = [
        json.loads(line)
        for line in Path(args.annotations).read_text().splitlines()
        if line.strip()
    ]
    answer_key = (
        json.loads(Path(args.answer_key).read_text())["answers"] if args.answer_key else None
    )
    result = score_human_agreement(
        annotations,
        answer_key=answer_key,
        kappa_threshold=args.kappa_threshold,
        gold_accuracy_threshold=args.gold_accuracy_threshold,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cogmembench")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.set_defaults(func=cmd_inspect)
    generate = sub.add_parser("generate")
    generate.add_argument("--scale", default="smoke")
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--output")
    generate.add_argument(
        "--generator-seeds",
        help="comma-separated scenario generator seeds; defaults to the scale configuration",
    )
    generate.add_argument(
        "--generator-version",
        choices=["development-v2", "cognitive-v2"],
    )
    generate.add_argument("--v2-variants", type=int)
    generate.add_argument(
        "--family",
        choices=[
            "all",
            "bitemporal_belief_revision",
            "recursive_investigation",
            "decision_lineage",
        ],
        default="all",
        help="cognitive-v2 family selection; ignored by compatibility generators",
    )
    generate.set_defaults(func=cmd_generate)
    run = sub.add_parser("run")
    run.add_argument("--scale", default="smoke")
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--model", default="deterministic-v1")
    run.add_argument("--conditions", default=",".join(CORE_CONDITIONS))
    run.add_argument(
        "--backend",
        choices=["reference", "mindgraph-local", "mindgraph-cloud"],
        default="reference",
    )
    run.add_argument("--provider-base-url")
    run.add_argument("--scenarios")
    run.add_argument("--resume", action="store_true")
    run.add_argument("--run-id")
    run.add_argument("--protocol-lock")
    run.set_defaults(func=cmd_run)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--run-id", required=True)
    evaluate.set_defaults(func=cmd_evaluate)
    report = sub.add_parser("report")
    report.add_argument("--run-id", required=True)
    report.set_defaults(func=cmd_report)
    compare = sub.add_parser("compare")
    compare.add_argument("--run-ids", required=True)
    compare.add_argument("--output-id", required=True)
    compare.set_defaults(func=cmd_compare)
    replay = sub.add_parser("replay")
    replay.add_argument("--scenario", required=True)
    replay.add_argument("--condition", choices=CONDITIONS, required=True)
    replay.add_argument("--scale", default="smoke")
    replay.add_argument("--seed", type=int, default=42)
    replay.add_argument("--model", default="deterministic-v1")
    replay.add_argument("--backend", default="reference")
    replay.add_argument("--scenarios")
    replay.set_defaults(func=cmd_replay)
    export = sub.add_parser("export-trajectories")
    export.add_argument("--run-id", required=True)
    export.set_defaults(func=cmd_export)
    validate_cognitive = sub.add_parser("validate-cognitive-v2")
    validate_cognitive.add_argument("--scenarios", required=True)
    validate_cognitive.add_argument("--output")
    validate_cognitive.set_defaults(func=cmd_validate_cognitive_v2)
    validate_generators = sub.add_parser("validate-generators-v2")
    validate_generators.add_argument("--scenarios", required=True)
    validate_generators.add_argument("--output")
    validate_generators.add_argument("--min-scenarios-per-family", type=int, default=5)
    validate_generators.add_argument("--min-templates-per-family", type=int, default=3)
    validate_generators.add_argument("--min-worlds-per-family", type=int, default=5)
    validate_generators.add_argument("--min-difficulty-tiers-per-family", type=int, default=3)
    validate_generators.add_argument("--min-unique-world-ratio", type=float, default=0.8)
    validate_generators.add_argument("--max-template-share", type=float, default=0.4)
    validate_generators.set_defaults(func=cmd_validate_generators_v2)
    validate_evaluators = sub.add_parser("validate-evaluators-v2")
    validate_evaluators.add_argument("--output")
    validate_evaluators.set_defaults(func=cmd_validate_evaluators_v2)
    validate_counterfactuals = sub.add_parser("validate-counterfactuals-v2")
    validate_counterfactuals.add_argument("--scenarios", required=True)
    validate_counterfactuals.add_argument("--output")
    validate_counterfactuals.set_defaults(func=cmd_validate_counterfactuals_v2)
    validate_adapter = sub.add_parser("validate-adapter-v2")
    validate_adapter.add_argument(
        "--adapter",
        choices=[
            "reference",
            "flat",
            "summary",
            "vector",
            "hybrid",
            "mindgraph-v2",
            "mem0-oss",
            "zep-cloud",
            "cognee",
        ],
        required=True,
    )
    validate_adapter.add_argument("--base-url")
    validate_adapter.add_argument(
        "--embedding-provider",
        choices=["deterministic", "openai"],
        default="deterministic",
    )
    validate_adapter.add_argument("--portability-audit", action="store_true")
    validate_adapter.set_defaults(func=cmd_validate_adapter_v2)
    run_cognitive = sub.add_parser("run-cognitive-v2")
    run_cognitive.add_argument("--scenarios", required=True)
    run_cognitive.add_argument("--model", default="deterministic-v1")
    run_cognitive.add_argument(
        "--conditions",
        default=",".join(COGNITIVE_V2_CONDITIONS),
    )
    run_cognitive.add_argument(
        "--scaffold",
        choices=["canonical-v1", "minimal-v1"],
        default="canonical-v1",
        help="versioned reasoning scaffold for the preregistered robustness subsample",
    )
    run_cognitive.add_argument(
        "--adapter",
        choices=[
            "reference",
            "flat",
            "summary",
            "vector",
            "hybrid",
            "mindgraph-v2",
            "mem0-oss",
            "zep-cloud",
            "cognee",
        ],
        default="reference",
    )
    run_cognitive.add_argument("--seed", type=int, default=42)
    run_cognitive.add_argument("--run-id")
    run_cognitive.add_argument("--results-root")
    run_cognitive.add_argument("--provider-base-url")
    run_cognitive.add_argument("--retrieval-k", type=int, default=8)
    run_cognitive.add_argument("--retrieval-tokens", type=int, default=1200)
    run_cognitive.add_argument(
        "--operating-mode",
        choices=["matched-budget", "natural"],
        default="matched-budget",
        help=(
            "labels the frozen comparison regime; natural mode uses the explicitly supplied "
            "adapter settings and still records complete observable accounting"
        ),
    )
    run_cognitive.add_argument(
        "--ablation",
        choices=[feature.value for feature in AblationFeature],
        help="remove exactly one substrate or policy feature for a causal ablation run",
    )
    run_cognitive.set_defaults(func=cmd_run_cognitive_v2)
    report_cognitive = sub.add_parser("report-cognitive-v2")
    report_cognitive.add_argument("--run-id", required=True)
    report_cognitive.add_argument("--results-root")
    report_cognitive.add_argument("--previous-run-id")
    report_cognitive.add_argument("--metric", default="task_success")
    report_cognitive.add_argument("--bootstrap-iterations", type=int, default=2000)
    report_cognitive.add_argument("--bootstrap-seed", type=int, default=1729)
    report_cognitive.set_defaults(func=cmd_report_cognitive_v2)
    analyze_cognitive = sub.add_parser("analyze-cognitive-v2")
    analyze_cognitive.add_argument(
        "--evaluated",
        required=True,
        help="comma-separated evaluated JSONL paths; combine full and ablation runs here",
    )
    analyze_cognitive.add_argument("--metric", default="task_success")
    analyze_cognitive.add_argument("--baseline-cell", default="stateless")
    analyze_cognitive.add_argument("--bootstrap-iterations", type=int, default=2000)
    analyze_cognitive.add_argument("--bootstrap-seed", type=int, default=1729)
    analyze_cognitive.add_argument("--calibration-bins", type=int, default=10)
    analyze_cognitive.add_argument("--output")
    analyze_cognitive.set_defaults(func=cmd_analyze_cognitive_v2)
    cost_cognitive = sub.add_parser("cost-cognitive-v2")
    cost_cognitive.add_argument("--evaluated", required=True)
    cost_cognitive.add_argument(
        "--profile", choices=["lite", "iteration", "publication"], default="iteration"
    )
    cost_cognitive.add_argument("--output")
    cost_cognitive.set_defaults(func=cmd_cost_cognitive_v2)
    power_cognitive = sub.add_parser("power-cognitive-v2")
    power_cognitive.add_argument("--evaluated", required=True)
    power_cognitive.add_argument("--metric", default="task_success")
    power_cognitive.add_argument("--treatment", default="automatic-passive")
    power_cognitive.add_argument("--baseline", default="transcript")
    power_cognitive.add_argument("--minimum-effect", type=float, required=True)
    power_cognitive.add_argument("--alpha", type=float, default=0.05)
    power_cognitive.add_argument("--target-power", type=float, default=0.8)
    power_cognitive.add_argument("--comparisons", type=int, default=1)
    power_cognitive.add_argument("--tier-field", default="difficulty_tier")
    power_cognitive.add_argument("--assumed-sd", type=float)
    power_cognitive.add_argument("--minimum-pilot-pairs", type=int, default=12)
    power_cognitive.add_argument("--frozen-pilot", action="store_true")
    power_cognitive.add_argument("--output")
    power_cognitive.set_defaults(func=cmd_power_cognitive_v2)
    failures_cognitive = sub.add_parser("failures-cognitive-v2")
    failures_cognitive.add_argument("--evaluated", required=True)
    failures_cognitive.add_argument("--output")
    failures_cognitive.set_defaults(func=cmd_failures_cognitive_v2)
    prepare_release_v2 = sub.add_parser("prepare-cognitive-v2-release")
    prepare_release_v2.add_argument("--scenarios", required=True)
    prepare_release_v2.add_argument(
        "--split",
        choices=["unit", "development", "calibration", "publication", "challenge"],
        required=True,
    )
    prepare_release_v2.add_argument("--reference", action="append")
    prepare_release_v2.add_argument("--canary-guid")
    prepare_release_v2.add_argument("--ngram-size", type=int, default=8)
    prepare_release_v2.add_argument("--output", required=True)
    prepare_release_v2.set_defaults(func=cmd_prepare_release_v2)
    freeze_v2 = sub.add_parser("freeze-cognitive-v2-protocol")
    freeze_mode = freeze_v2.add_mutually_exclusive_group(required=True)
    freeze_mode.add_argument("--spec")
    freeze_v2.add_argument("--output")
    freeze_mode.add_argument("--verify")
    freeze_v2.set_defaults(func=cmd_freeze_protocol_v2)
    annotations_v2 = sub.add_parser("export-cognitive-v2-annotations")
    annotations_v2.add_argument("--scenarios", required=True)
    annotations_v2.add_argument("--sample-size", type=int, default=50)
    annotations_v2.add_argument("--seed", type=int, default=1729)
    annotations_v2.add_argument("--output", required=True)
    annotations_v2.add_argument("--answer-key", required=True)
    annotations_v2.set_defaults(func=cmd_export_annotations_v2)
    agreement_v2 = sub.add_parser("agreement-cognitive-v2")
    agreement_v2.add_argument("--annotations", required=True)
    agreement_v2.add_argument("--answer-key")
    agreement_v2.add_argument("--kappa-threshold", type=float, default=0.8)
    agreement_v2.add_argument("--gold-accuracy-threshold", type=float, default=0.9)
    agreement_v2.add_argument("--output")
    agreement_v2.set_defaults(func=cmd_agreement_v2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
