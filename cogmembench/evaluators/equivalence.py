from __future__ import annotations

import json
import re
from typing import Any

HEDGE_PREFIXES = (
    "according to available evidence",
    "based on available evidence",
    "with current evidence",
    "my best estimate is",
    "it appears that",
    "appears to be",
    "i believe",
    "uncertain but",
    "provisionally",
    "probably",
    "likely",
)

EQUIVALENCES = {
    "corrected": ("revised", "updated"),
    "provisional": ("initial", "preliminary", "as known then", "original belief"),
    "stored conclusion": (
        "stored derived conclusion",
        "previously derived conclusion",
        "prior derived conclusion",
    ),
    "minimize user impact": (
        "reduce user impact",
        "minimize customer impact",
        "reduce customer disruption",
    ),
}

REMEDIATION_VERBS = {
    "increase": ("raise", "expand"),
    "flush": ("clear",),
    "rotate": ("replace", "renew"),
    "restart": ("recycle",),
    "promote": ("fail over to",),
}

CONFLICT = re.compile(r"\b(?:not|neither|either)\b|\sor\s", re.I)


def normalize_text(value: Any) -> str:
    text = str(value).lower().replace("_", " ").replace("-", " ")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _strip_hedging(value: str) -> str:
    normalized = normalize_text(value)
    changed = True
    while changed:
        changed = False
        for prefix in HEDGE_PREFIXES:
            normalized_prefix = normalize_text(prefix)
            if normalized == normalized_prefix:
                continue
            if normalized.startswith(normalized_prefix + " "):
                normalized = normalized[len(normalized_prefix) :].strip()
                changed = True
                break
    return normalized


def phrase_variants(expected: Any) -> set[str]:
    normalized = normalize_text(expected)
    variants = {normalized}
    variants.update(normalize_text(value) for value in EQUIVALENCES.get(normalized, ()))
    first, separator, remainder = normalized.partition(" ")
    if separator and first in REMEDIATION_VERBS:
        variants.update(
            normalize_text(f"{replacement} {remainder}")
            for replacement in REMEDIATION_VERBS[first]
        )
    return variants


def equivalent_value(actual: Any, expected: Any) -> bool:
    """Strict deterministic equivalence with bounded hedging and granularity rules."""
    if isinstance(expected, bool):
        return actual is expected
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return actual == expected
    if isinstance(actual, (list, tuple)):
        if isinstance(expected, (list, tuple)):
            return len(actual) == len(expected) and all(
                any(equivalent_value(item, target) for item in actual) for target in expected
            )
        return len(actual) == 1 and equivalent_value(actual[0], expected)
    if isinstance(expected, (list, tuple)):
        return len(expected) == 1 and equivalent_value(actual, expected[0])
    normalized = _strip_hedging(str(actual))
    if CONFLICT.search(normalized):
        return False
    return normalized in phrase_variants(expected)


def contains_equivalent_phrase(actual: Any, expected: Any) -> bool:
    normalized = normalize_text(actual)
    if CONFLICT.search(normalized):
        return False
    padded = f" {normalized} "
    return any(f" {candidate} " in padded for candidate in phrase_variants(expected))


def parse_json_object(answer: str) -> dict[str, Any]:
    try:
        value = json.loads(answer)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def structured_field_accuracy(
    answer: str,
    expected: dict[str, Any],
) -> tuple[float, dict[str, bool]]:
    actual = parse_json_object(answer)
    checks = {key: equivalent_value(actual.get(key, ""), value) for key, value in expected.items()}
    return (sum(checks.values()) / len(checks) if checks else 0.0), checks


def calibration_metrics(answer: str, correctness: float) -> dict[str, float | None]:
    actual = parse_json_object(answer)
    confidence = actual.get("confidence")
    valid_confidence = (
        isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and 0 <= confidence <= 1
    )
    unknown = any(
        normalize_text(value) in {"unknown", "insufficient evidence", "unavailable"}
        for key, value in actual.items()
        if key != "confidence"
    )
    return {
        "confidence_brier": (
            (float(confidence) - correctness) ** 2 if valid_confidence else None
        ),
        "confidence_available": float(valid_confidence),
        "confidence_value": float(confidence) if valid_confidence else None,
        "inappropriate_abstention": float(unknown),
    }
