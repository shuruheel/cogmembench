from __future__ import annotations

import random

from ..schema import Event, EvaluatorSpec, ExpectedMemory, PublicScenario, Scenario

FAMILIES = (
    "preference_continuity",
    "belief_revision",
    "project_continuation",
    "failure_learning",
)

TRANSPORT = [("train", "rental car"), ("bus", "rideshare"), ("bicycle", "scooter")]
AVOIDS = ["red-eye departures", "tight connections", "unsealed roads", "meetings before 9 AM"]
PROJECTS = ["Atlas", "Juniper", "Kestrel", "Lumen", "Mosaic"]
DELIMITERS = [
    ("comma", "CSV parser"),
    ("pipe", "quoted pipe-delimited parser"),
    ("semicolon", "quoted semicolon-delimited parser"),
]


def _events(rows: list[tuple[str, str, bool]]) -> tuple[Event, ...]:
    counts: dict[str, int] = {}
    out = []
    for session, content, evaluate in rows:
        counts[session] = counts.get(session, 0) + 1
        out.append(Event(session, counts[session], "user", content, evaluate))
    return tuple(out)


def preference(seed: int, variant: int, max_steps: int) -> Scenario:
    rng = random.Random(seed * 1009 + variant)
    old, new = TRANSPORT[variant % len(TRANSPORT)]
    avoid = AVOIDS[(variant + seed) % len(AVOIDS)]
    person = f"Traveler-{rng.randrange(100, 999)}"
    sid = f"preference-{seed}-{variant:02d}"
    events = _events([
        ("s1", f"For {person}'s regional trips, prefer {old}. Always avoid {avoid}.", False),
        ("s1", f"Temporary detail: today's lobby code is {rng.randrange(1000,9999)}; do not retain it.", False),
        ("s2", "Exception: walking is fine for trips under 3 miles, but it does not change the regional-trip preference.", False),
        ("s3", f"Correction: {person} now prefers {new} instead of {old} for regional trips. This supersedes the earlier preference.", False),
        ("s4", f"Recommend transport for {person}'s 20-mile regional trip. Return only JSON with keys choice, avoid, basis.", True),
    ])
    old_id, new_id, avoid_id = f"{sid}:old", f"{sid}:new", f"{sid}:avoid"
    durable = (
        ExpectedMemory(old_id, "preference", f"regional transport preference was {old}", "transport", old, "s1"),
        ExpectedMemory(avoid_id, "preference", f"avoid {avoid}", "avoid", avoid, "s1"),
        ExpectedMemory(new_id, "preference", f"correction: regional transport preference is {new}", "transport", new, "s3", old_id),
    )
    return Scenario(
        PublicScenario(sid, "preference_continuity", seed, variant, events, max_steps),
        EvaluatorSpec(
            {"choice": new, "avoid": avoid, "basis": "corrected preference"},
            durable,
            obsolete_values=(old,),
            non_durable_terms=("lobby code",),
            expected_retrieval_ids=(new_id, avoid_id),
            expected_tool_ops=("retrieve", "preference", "supersede"),
            category="continuity",
        ),
        {"person": person, "active_transport": new},
    )


def belief(seed: int, variant: int, max_steps: int) -> Scenario:
    project = PROJECTS[variant % len(PROJECTS)]
    old_day = 10 + (variant % 8)
    new_day = old_day + 9
    sid = f"belief-{seed}-{variant:02d}"
    events = _events([
        ("s1", f"Source Alpha says {project} launches in the US on March {old_day}. Treat this as a provisional claim with Alpha as evidence.", False),
        ("s2", f"Alpha retracted that date. Authoritative release bulletin Beta says {project} launches in the US on March {new_day}; it gives no Europe date.", False),
        ("s2", "A forum repeats the old date but cites only Alpha's retracted post.", False),
        ("s3", f"What is the current belief about {project}'s launch? Return only JSON with launch_date, region, old_claim_status, evidence, europe_status.", True),
    ])
    claim_old, ev_alpha, claim_new, ev_beta = (f"{sid}:{x}" for x in ("claim-old", "ev-alpha", "claim-new", "ev-beta"))
    durable = (
        ExpectedMemory(claim_old, "claim", f"{project} US launch March {old_day}", "launch", f"March {old_day}", "s1", provenance=(ev_alpha,)),
        ExpectedMemory(ev_alpha, "evidence", "Source Alpha provisional report", source_session="s1"),
        ExpectedMemory(claim_new, "claim", f"Alpha retracted the old date; corrected {project} US launch is March {new_day}", "launch", f"March {new_day}", "s2", claim_old, (ev_beta,)),
        ExpectedMemory(ev_beta, "evidence", "Authoritative Beta release bulletin", source_session="s2"),
    )
    return Scenario(
        PublicScenario(sid, "belief_revision", seed, variant, events, max_steps),
        EvaluatorSpec(
            {"launch_date": f"March {new_day}", "region": "US", "old_claim_status": "retracted", "evidence": "Beta", "europe_status": "unknown"},
            durable,
            obsolete_values=(f"March {old_day}",),
            expected_retrieval_ids=(claim_new, ev_beta, claim_old),
            expected_tool_ops=("retrieve", "claim", "evidence", "supersede"),
            category="belief",
        ),
        {"current_date": f"March {new_day}", "scope": "US"},
    )


def project(seed: int, variant: int, max_steps: int) -> Scenario:
    name = PROJECTS[variant % len(PROJECTS)]
    schema = f"schema-v{variant + 2}"
    sid = f"project-{seed}-{variant:02d}"
    events = _events([
        ("s1", f"Project {name}: objective is ship a telemetry importer. Tasks: design mapping, implement parser, run validation, deploy. Parser depends on mapping; validation depends on parser; deploy depends on validation.", False),
        ("s1", "Decision: use streaming parsing to stay below the memory limit.", False),
        ("s2", f"Design mapping completed. Parser attempt failed because the input lacked a declared schema. Requirement changed: validate against {schema} before parsing.", False),
        ("s2", "The color of the temporary status board is teal; this is not project state.", False),
        ("s3", f"Resume project {name}. Return only JSON with completed, failed, next_action, decision, avoid_repeat.", True),
    ])
    objective, decision, done, failed, next_task = (f"{sid}:{x}" for x in ("objective", "decision", "done", "failed", "next"))
    durable = (
        ExpectedMemory(objective, "goal", f"ship {name} telemetry importer", source_session="s1"),
        ExpectedMemory(decision, "decision", "use streaming parsing", source_session="s1"),
        ExpectedMemory(done, "task", "design mapping completed", "task_status", "completed", "s2"),
        ExpectedMemory(failed, "execution", "parser failed without declared schema", "task_status", "failed", "s2"),
        ExpectedMemory(next_task, "task", f"validate input against {schema}", "task_status", "next", "s2"),
    )
    return Scenario(
        PublicScenario(sid, "project_continuation", seed, variant, events, max_steps),
        EvaluatorSpec(
            {"completed": "design mapping", "failed": "parser", "next_action": f"validate against {schema}", "decision": "streaming parsing", "avoid_repeat": "parse without schema"},
            durable,
            non_durable_terms=("teal",),
            expected_retrieval_ids=(done, failed, next_task, decision),
            expected_tool_ops=("retrieve", "goal", "decision", "task", "execution"),
            category="recovery",
        ),
        {"next_executable": f"validate against {schema}"},
    )


def failure(seed: int, variant: int, max_steps: int) -> Scenario:
    broken, replacement = DELIMITERS[variant % len(DELIMITERS)]
    sid = f"failure-{seed}-{variant:02d}"
    events = _events([
        ("s1", f"We tried parsing vendor exports by splitting every line on {broken}. It failed because quoted fields can contain {broken} delimiters. The lesson applies to delimited text with quoting.", False),
        ("s2", f"New similar task: import another quoted delimited export. A robust {replacement} is available.", False),
        ("s2", "Control task: decode a fixed-width binary header; it has no delimiters or quoted fields.", False),
        ("s3", "Choose approaches for both tasks. Return only JSON with similar_method, control_method, failure_cause, scope.", True),
    ])
    failure_id, lesson_id, similar_id, control_id = (
        f"{sid}:{suffix}"
        for suffix in ("failure", "lesson", "similar-task", "control-task")
    )
    durable = (
        ExpectedMemory(failure_id, "execution", f"split-on-{broken} failed with quoted delimiters", source_session="s1"),
        ExpectedMemory(lesson_id, "policy", "use robust parser for quoted delimited text; not binary", source_session="s1", provenance=(failure_id,)),
        ExpectedMemory(
            similar_id,
            "task",
            f"quoted delimited export should use robust {replacement}",
            "task_status",
            "next",
            "s2",
        ),
        ExpectedMemory(
            control_id,
            "task",
            "fixed-width binary header should use fixed-width binary decoder; no delimiters or quoting",
            "task_status",
            "next",
            "s2",
        ),
    )
    return Scenario(
        PublicScenario(sid, "failure_learning", seed, variant, events, max_steps),
        EvaluatorSpec(
            {"similar_method": replacement, "control_method": "fixed-width binary decoder", "failure_cause": "quoted delimiter", "scope": "delimited text only"},
            durable,
            obsolete_values=(f"split on {broken}",),
            expected_retrieval_ids=(failure_id, lesson_id, similar_id, control_id),
            expected_tool_ops=("retrieve", "execution", "policy", "task"),
            category="failure_learning",
        ),
        {"transfer": replacement, "control": "fixed-width binary decoder"},
    )


GENERATORS = {
    "preference_continuity": preference,
    "belief_revision": belief,
    "project_continuation": project,
    "failure_learning": failure,
}


def generate_suite(scale: str, base_seed: int, variants: int, seeds: list[int], max_steps: int) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for cohort in seeds:
        seed = base_seed * 10_000 + cohort
        for family in FAMILIES:
            for variant in range(variants):
                scenarios.append(GENERATORS[family](seed, variant, max_steps))
    return scenarios
