from __future__ import annotations

import random
from typing import Any

from ..schema import (
    Event,
    EvaluatorSpec,
    ExpectedAction,
    ExpectedMemory,
    PublicScenario,
    Scenario,
)


PREFERENCE_CASES = (
    ("regional transport", "train", "rental car", "unsealed roads", "under 3 miles", "walking"),
    ("status updates", "long email", "three bullets", "weekend messages", "security incidents", "immediate alert"),
    ("team meetings", "afternoon", "morning", "before 9 AM", "incident reviews", "afternoon"),
    ("data analysis", "spreadsheets", "Python", "proprietary macros", "quick one-row edits", "spreadsheet"),
    ("work travel", "hotel", "apartment", "shared bathrooms", "single-night stays", "hotel"),
    ("meal planning", "vegetarian", "vegan", "peanuts", "medical recovery", "vegetarian"),
    ("code review", "inline comments", "summary first", "style-only blocking", "security defects", "inline comments"),
    ("calendar booking", "30-minute blocks", "45-minute blocks", "lunch meetings", "urgent customer calls", "30-minute block"),
    ("documentation", "tutorials", "reference pages", "unversioned examples", "new contributors", "tutorial"),
    ("deployment", "manual approval", "automated approval", "Friday releases", "critical patches", "manual approval"),
)

BELIEF_CASES = (
    ("Atlas", "US launch date", "March 12", "March 21", "US", "Europe", "Alpha", "Beta"),
    ("Juniper", "supported database", "MySQL", "PostgreSQL", "version 4", "version 3", "old README", "release notes"),
    ("Kestrel", "filing deadline", "June 1", "June 15", "New York", "California", "memo A", "regulator bulletin"),
    ("Lumen", "service owner", "Team North", "Team East", "production", "staging", "directory", "incident record"),
    ("Mosaic", "retention period", "30 days", "90 days", "audit logs", "debug logs", "draft policy", "approved policy"),
    ("Orchid", "API limit", "100 rpm", "240 rpm", "enterprise tier", "free tier", "forum", "provider dashboard"),
    ("Pioneer", "meeting date", "April 8", "April 11", "board meeting", "committee meeting", "calendar export", "signed notice"),
    ("Quartz", "package license", "MIT", "Apache-2.0", "version 2", "version 1", "cached registry", "source repository"),
    ("Raven", "regional lead", "Morgan Lee", "Morgan Liu", "EMEA", "APAC", "contact sheet", "HR directory"),
    ("Summit", "temperature limit", "70 C", "85 C", "rev-B hardware", "rev-A hardware", "datasheet draft", "certified datasheet"),
)

PROJECT_CASES = (
    ("Atlas", "telemetry importer", "design mapping", "implement parser", "validate schema-v2", "streaming parsing", "missing schema"),
    ("Juniper", "billing migration", "inventory tables", "write migration", "rehearse rollback", "dual writes", "missing rollback"),
    ("Kestrel", "mobile release", "freeze scope", "build candidate", "run device tests", "phased rollout", "unsigned build"),
    ("Lumen", "search upgrade", "capture baseline", "replace index", "compare relevance", "shadow traffic", "no baseline"),
    ("Mosaic", "compliance audit", "map controls", "collect evidence", "review exceptions", "evidence first", "missing owner"),
    ("Orchid", "warehouse move", "label inventory", "move racks", "reconcile counts", "zone sequencing", "duplicate labels"),
    ("Pioneer", "support launch", "define routing", "train responders", "run simulation", "regional queues", "stale playbook"),
    ("Quartz", "SDK release", "lock API", "generate clients", "run compatibility", "semantic versioning", "breaking rename"),
    ("Raven", "incident review", "build timeline", "verify causes", "publish actions", "evidence before blame", "clock skew"),
    ("Summit", "data retention change", "classify datasets", "apply policies", "verify deletion", "dry-run deletion", "unclassified backup"),
)

FAILURE_CASES = (
    ("comma splitting", "quoted commas", "CSV parser", "fixed-width header", "fixed-width decoder", "delimited text"),
    ("blind retries", "non-idempotent writes", "idempotency key", "read-only lookup", "ordinary retry", "mutating requests"),
    ("global cache", "tenant data leakage", "tenant-scoped key", "public catalog", "shared cache", "tenant data"),
    ("UTC assumption", "local daylight transition", "timezone-aware conversion", "elapsed seconds", "duration arithmetic", "civil time"),
    ("float currency", "rounding accumulation", "decimal arithmetic", "sensor average", "floating point", "money"),
    ("filename identity", "renamed duplicate files", "content hash", "unique generated file", "filename", "deduplication"),
    ("unbounded concurrency", "provider throttling", "bounded worker pool", "local CPU batch", "parallel map", "rate-limited I/O"),
    ("schema inference", "empty first batch", "declared schema", "free-form notes", "text ingestion", "structured imports"),
    ("last-write-wins", "concurrent edits", "version check", "single-writer log", "append", "concurrent mutable state"),
    ("substring authorization", "ambiguous resource names", "resource ID check", "display filtering", "substring match", "authorization"),
)


def _events(rows: list[tuple[str, str, str | None]]) -> tuple[Event, ...]:
    turns: dict[str, int] = {}
    events = []
    for session_id, content, checkpoint_id in rows:
        turns[session_id] = turns.get(session_id, 0) + 1
        events.append(
            Event(
                session_id,
                turns[session_id],
                "user",
                content,
                evaluate=checkpoint_id is not None,
                checkpoint_id=checkpoint_id,
            )
        )
    return tuple(events)


def _preference(seed: int, variant: int, max_steps: int) -> Scenario:
    domain, old, new, avoid, exception_scope, exception_choice = PREFERENCE_CASES[variant]
    person = f"User-{random.Random(seed * 1009 + variant).randrange(1000, 9999)}"
    sid = f"preference-v2-{seed}-{variant:02d}"
    old_id, avoid_id, new_id, exception_id = (f"{sid}:{name}" for name in ("old", "avoid", "new", "exception"))
    events = _events(
        [
            ("s1", f"For {person}, the default for {domain} is {old}. Always avoid {avoid}.", None),
            ("s1", "Temporary note: the blue access badge expires tonight; do not retain this.", None),
            ("s2", f"Narrow exception: for {exception_scope}, use {exception_choice}; this does not change the default.", None),
            ("s3", f"Correction: {person}'s default for {domain} is now {new}, replacing {old}. Preserve the narrow exception.", None),
            ("s4", f"Apply {person}'s current default for {domain}. Return only JSON with keys choice, avoid, basis.", "default"),
            ("s5", f"Now apply the {exception_scope} case for {person}. Return only JSON with keys choice, avoid, basis.", "exception"),
        ]
    )
    durable = (
        ExpectedMemory(old_id, "preference", f"default {domain} was {old}", source_session="s1"),
        ExpectedMemory(avoid_id, "preference", f"avoid {avoid}", source_session="s1"),
        ExpectedMemory(exception_id, "preference", f"for {exception_scope} use {exception_choice}", source_session="s2"),
        ExpectedMemory(new_id, "preference", f"corrected default {domain} is {new}", source_session="s3", supersedes=old_id),
    )
    actions = (
        ExpectedAction("s1", 1, "write", "preference", (old_id, avoid_id)),
        ExpectedAction("s2", 1, "write", "preference", (exception_id,)),
        ExpectedAction("s3", 1, "write", "preference", (new_id,)),
        ExpectedAction("s4", 1, "retrieve", memory_ids=(new_id, avoid_id)),
        ExpectedAction("s5", 1, "retrieve", memory_ids=(exception_id, avoid_id)),
    )
    expected_answers = {
        "default": {"choice": new, "avoid": avoid, "basis": "corrected preference"},
        "exception": {"choice": exception_choice, "avoid": avoid, "basis": "narrow exception"},
    }
    return Scenario(
        PublicScenario(sid, "preference_continuity", seed, variant, events, max_steps),
        EvaluatorSpec(
            expected_answers["exception"],
            durable,
            expected_answers=expected_answers,
            expected_actions=actions,
            obsolete_values=(old,),
            non_durable_terms=("blue access badge",),
            expected_retrieval_ids=(new_id, avoid_id, exception_id),
            expected_tool_ops=("retrieve", "journal"),
            category="continuity",
        ),
        {"person": person, "active_default": new, "exception": exception_choice},
    )


def _belief(seed: int, variant: int, max_steps: int) -> Scenario:
    project, subject, old, new, scope, unknown_scope, weak, strong = BELIEF_CASES[variant]
    sid = f"belief-v2-{seed}-{variant:02d}"
    claim_old, ev_old, claim_new, ev_new = (f"{sid}:{name}" for name in ("claim-old", "evidence-old", "claim-new", "evidence-new"))
    events = _events(
        [
            ("s1", f"{weak} reports that {project}'s {subject} is {old} for {scope}. Treat it as provisional evidence.", None),
            ("s2", f"{weak} was retracted. Authoritative {strong} establishes {new} for {scope}. It says nothing about {unknown_scope}.", None),
            ("s2", f"An aggregator repeats {old}, citing only the retracted {weak}.", None),
            ("s3", f"State the current belief about {project}. Return only JSON with keys value, scope, old_claim_status, evidence, unknown_scope_status.", "belief"),
            ("s4", f"Audit the basis for {project}'s current {subject}. Return only JSON with keys value, scope, old_claim_status, evidence, unknown_scope_status.", "audit"),
        ]
    )
    durable = (
        ExpectedMemory(claim_old, "claim", f"{project} {subject} {old} for {scope}", source_session="s1", provenance=(ev_old,)),
        ExpectedMemory(ev_old, "evidence", f"provisional {weak}", source_session="s1"),
        ExpectedMemory(claim_new, "claim", f"corrected {project} {subject} {new} for {scope}", source_session="s2", supersedes=claim_old, provenance=(ev_new,)),
        ExpectedMemory(ev_new, "evidence", f"authoritative {strong}", source_session="s2"),
    )
    expected = {"value": new, "scope": scope, "old_claim_status": "retracted", "evidence": strong, "unknown_scope_status": "unknown"}
    actions = (
        ExpectedAction("s1", 1, "write", "claim", (claim_old, ev_old)),
        ExpectedAction("s2", 1, "write", "claim", (claim_new, ev_new)),
        ExpectedAction("s3", 1, "retrieve", memory_ids=(claim_new, ev_new, claim_old)),
        ExpectedAction("s4", 1, "retrieve", memory_ids=(claim_new, ev_new, claim_old)),
    )
    return Scenario(
        PublicScenario(sid, "belief_revision", seed, variant, events, max_steps),
        EvaluatorSpec(
            expected,
            durable,
            expected_answers={"belief": expected, "audit": expected},
            expected_actions=actions,
            obsolete_values=(old,),
            expected_retrieval_ids=(claim_new, ev_new, claim_old),
            expected_tool_ops=("retrieve", "claim"),
            category="belief",
        ),
        {"current_value": new, "scope": scope, "unknown_scope": unknown_scope},
    )


def _project(seed: int, variant: int, max_steps: int) -> Scenario:
    name, objective_text, done_text, failed_text, next_text, decision_text, cause = PROJECT_CASES[variant]
    sid = f"project-v2-{seed}-{variant:02d}"
    objective, decision, done, failed, next_id, later = (f"{sid}:{name}" for name in ("objective", "decision", "done", "failed", "next", "later"))
    events = _events(
        [
            ("s1", f"Project {name}: objective is {objective_text}. Sequence: {done_text}, then {failed_text}, then {next_text}, then release.", None),
            ("s1", f"Decision: use {decision_text}.", None),
            ("s2", f"{done_text} completed. The attempt to {failed_text} failed because of {cause}. The next executable action is {next_text}.", None),
            ("s2", "Temporary status-screen color is amber; it is not project state.", None),
            ("s3", f"Resume {name}. Return only JSON with completed, failed, next_action, decision, avoid_repeat.", "resume"),
            ("s4", f"Update: {next_text} is now completed. Release remains pending.", None),
            ("s5", f"Resume {name} again. Return only JSON with completed, failed, next_action, decision, avoid_repeat.", "after_update"),
        ]
    )
    durable = (
        ExpectedMemory(objective, "goal", objective_text, source_session="s1"),
        ExpectedMemory(decision, "decision", decision_text, source_session="s1"),
        ExpectedMemory(done, "task", f"{done_text} completed", value="completed", source_session="s2"),
        ExpectedMemory(failed, "execution", f"{failed_text} failed because {cause}", value="failed", source_session="s2"),
        ExpectedMemory(next_id, "task", f"next action {next_text}", value="next", source_session="s2"),
        ExpectedMemory(later, "task", f"{next_text} completed; release pending", value="completed", source_session="s4"),
    )
    first = {"completed": done_text, "failed": failed_text, "next_action": next_text, "decision": decision_text, "avoid_repeat": cause}
    second = {"completed": next_text, "failed": failed_text, "next_action": "release", "decision": decision_text, "avoid_repeat": cause}
    actions = (
        ExpectedAction("s1", 1, "write", "goal", (objective,)),
        ExpectedAction("s1", 2, "write", "decision", (decision,)),
        ExpectedAction("s2", 1, "write", "task", (done, failed, next_id)),
        ExpectedAction("s3", 1, "retrieve", memory_ids=(done, failed, next_id, decision)),
        ExpectedAction("s4", 1, "write", "task", (later,)),
        ExpectedAction("s5", 1, "retrieve", memory_ids=(later, failed, decision)),
    )
    return Scenario(
        PublicScenario(sid, "project_continuation", seed, variant, events, max_steps),
        EvaluatorSpec(
            second,
            durable,
            expected_answers={"resume": first, "after_update": second},
            expected_actions=actions,
            non_durable_terms=("amber",),
            expected_retrieval_ids=(done, failed, next_id, later, decision),
            expected_tool_ops=("retrieve", "goal", "open_decision", "create_task"),
            category="recovery",
        ),
        {"next_before": next_text, "next_after": "release"},
    )


def _failure(seed: int, variant: int, max_steps: int) -> Scenario:
    method, cause, replacement, control, control_method, scope = FAILURE_CASES[variant]
    sid = f"failure-v2-{seed}-{variant:02d}"
    failure_id, policy_id, similar_id, control_id = (f"{sid}:{name}" for name in ("failure", "policy", "similar", "control"))
    events = _events(
        [
            ("s1", f"We used {method}; it failed because of {cause}. The lesson applies to {scope}.", None),
            ("s2", f"Similar task: another {scope} case; {replacement} is available.", None),
            ("s2", f"Control task: {control}; use {control_method}. It is outside the lesson's scope.", None),
            ("s3", "Choose both approaches. Return only JSON with similar_method, control_method, failure_cause, scope.", "transfer"),
            ("s4", f"A second similar {scope} task arrived, while the same control remains unchanged.", None),
            ("s5", "Choose both approaches again. Return only JSON with similar_method, control_method, failure_cause, scope.", "reuse"),
        ]
    )
    durable = (
        ExpectedMemory(failure_id, "execution", f"{method} failed because {cause}", source_session="s1"),
        ExpectedMemory(policy_id, "policy", f"use {replacement} for {scope}; not the control", source_session="s1", provenance=(failure_id,)),
        ExpectedMemory(similar_id, "task", f"similar {scope} task use {replacement}", source_session="s2"),
        ExpectedMemory(control_id, "task", f"{control} use {control_method}", source_session="s2"),
    )
    expected = {"similar_method": replacement, "control_method": control_method, "failure_cause": cause, "scope": scope}
    actions = (
        ExpectedAction("s1", 1, "write", "execution", (failure_id, policy_id)),
        ExpectedAction("s2", 1, "write", "task", (similar_id,)),
        ExpectedAction("s2", 2, "write", "task", (control_id,)),
        ExpectedAction("s3", 1, "retrieve", memory_ids=(failure_id, policy_id, similar_id, control_id)),
        ExpectedAction("s5", 1, "retrieve", memory_ids=(failure_id, policy_id, similar_id, control_id)),
    )
    return Scenario(
        PublicScenario(sid, "failure_learning", seed, variant, events, max_steps),
        EvaluatorSpec(
            expected,
            durable,
            expected_answers={"transfer": expected, "reuse": expected},
            expected_actions=actions,
            obsolete_values=(method,),
            expected_retrieval_ids=(failure_id, policy_id, similar_id, control_id),
            expected_tool_ops=("retrieve", "fail_execution", "create_policy", "create_task"),
            category="failure_learning",
        ),
        {"transfer": replacement, "control": control_method},
    )


GENERATORS: tuple[Any, ...] = (_preference, _belief, _project, _failure)


def generate_development_v2(
    seed: int, max_steps: int = 8, variants_per_family: int = 10
) -> list[Scenario]:
    if not 1 <= variants_per_family <= 10:
        raise ValueError("development-v2 supports 1-10 structural variants per family")
    scenarios = []
    generated_seed = seed * 10_000 + 42
    for generator in GENERATORS:
        for variant in range(variants_per_family):
            scenarios.append(generator(generated_seed, variant, max_steps))
    return scenarios
