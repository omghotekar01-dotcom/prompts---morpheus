from __future__ import annotations

from typing import Any, Mapping


class ResearchPromotionError(ValueError):
    """Raised when research evidence is insufficient for runtime promotion."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ResearchPromotionError(message)


def verify_research_promotion(
    readiness: Mapping[str, Any],
    *,
    requested_features: list[str],
) -> dict[str, Any]:
    """Fail closed when restricted MORPHEUS research is requested for control.

    The readiness ledger is the source of truth: implementation alone is never
    treated as statistical validation. Every requested feature must exist and
    explicitly authorize automatic control.
    """

    _require(
        readiness.get("schema") == "morpheus-distribution-research-readiness-v1",
        "unsupported research readiness schema",
    )
    features = readiness.get("features")
    _require(isinstance(features, list), "readiness.features must be a list")
    _require(requested_features, "at least one research feature is required")
    _require(len(set(requested_features)) == len(requested_features), "duplicate requested research feature")

    by_name: dict[str, Mapping[str, Any]] = {}
    for item in features:
        _require(isinstance(item, Mapping), "readiness feature entry must be an object")
        name = item.get("feature")
        _require(isinstance(name, str) and name, "readiness feature must have a non-empty name")
        _require(name not in by_name, f"duplicate readiness feature: {name}")
        by_name[name] = item

    blocked: list[dict[str, str]] = []
    for name in requested_features:
        _require(isinstance(name, str) and name, "requested research feature must be a non-empty string")
        item = by_name.get(name)
        _require(item is not None, f"unknown research feature: {name}")
        allowed = item.get("automatic_control_allowed")
        _require(type(allowed) is bool, f"{name}.automatic_control_allowed must be boolean")
        if not allowed:
            blocker = item.get("blocker")
            blocked.append({
                "feature": name,
                "blocker": blocker if isinstance(blocker, str) and blocker else "independent validation required",
            })

    return {
        "promoted": not blocked,
        "requested_features": list(requested_features),
        "blocked_features": blocked,
        "decision": "ALLOW_AUTOMATIC_CONTROL" if not blocked else "RESEARCH_ONLY",
        "truth_boundary": "Only features explicitly authorized by the readiness ledger may influence automatic runtime control.",
    }
