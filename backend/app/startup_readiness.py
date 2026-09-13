from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .completion import engineering_completion_report


SCHEMA = "morpheus-startup-mvp-readiness-v1"
_LOCAL_PILOT_CHECK_IDS = (
    "durable_state_store",
    "content_addressed_artifact_store",
    "evidence_ledger_integrity",
    "durable_idempotency_journal",
    "no_ambiguous_idempotency_side_effects",
    "native_cpp20_toolchain",
)
_PILOT_CONFIGURATION_CHECK_IDS = frozenset({"api_key_guard", "request_rate_limit"})
_REQUIRED_PILOT_CAPABILITIES = (
    "fail_closed_pilot_readiness",
    "guarded_single_worker_pilot_launcher",
    "bounded_operational_observability",
    "durable_idempotent_pilot_synthesis",
    "manual_idempotency_resolution",
    "single_node_backup_restore",
    "pilot_browser_boundary",
)


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value.lower())


def _check(
    check_id: str,
    *,
    passed: bool,
    detail: str,
    evidence_state: str,
    source: str,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "required": True,
        "passed": bool(passed),
        "detail": detail,
        "evidence_state": evidence_state,
        "source": source,
    }


def _feature_policy_check(feature_registry: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    raw_features = feature_registry.get("features")
    features = [item for item in raw_features if isinstance(item, Mapping)] if isinstance(raw_features, list) else []
    by_id = {str(item.get("id")): item for item in features if item.get("id")}
    unsafe: list[str] = []
    for item in features:
        feature_id = str(item.get("id", "unknown"))
        maturity = str(item.get("maturity", ""))
        if maturity == "blocked" and item.get("default_enabled") is True:
            unsafe.append(f"{feature_id}:blocked_default_enabled")
        if maturity in {"research", "blocked"} and item.get("automatic_control_allowed") is True:
            unsafe.append(f"{feature_id}:unsafe_automatic_control")

    startup_gate = by_id.get("startup_readiness_gate")
    startup_gate_safe = bool(
        startup_gate
        and startup_gate.get("maturity") == "stable"
        and startup_gate.get("default_enabled") is True
        and startup_gate.get("automatic_control_allowed") is False
    )
    passed = bool(
        feature_registry.get("schema") == "morpheus-feature-registry-v1"
        and _is_sha256(feature_registry.get("sha256"))
        and features
        and startup_gate_safe
        and not unsafe
    )
    detail = (
        "Feature policy is canonical, startup readiness is stable, and research/blocked features remain fail-closed for automatic control."
        if passed
        else "Feature policy is missing, malformed, or grants authority outside the declared startup-MVP boundary."
    )
    return (
        _check(
            "feature_policy_integrity",
            passed=passed,
            detail=detail,
            evidence_state="STARTUP_MVP_FEATURE_POLICY_SAFE" if passed else "STARTUP_MVP_FEATURE_POLICY_BLOCKED",
            source="feature_registry",
        ),
        unsafe,
    )


def build_startup_mvp_readiness(
    *,
    capabilities: Mapping[str, Any],
    feature_registry: Mapping[str, Any],
    pilot_readiness: Mapping[str, Any],
    pilot_capabilities: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    api_contract_sha256: str,
    api_route_count: int,
) -> dict[str, Any]:
    """Compose a fail-closed readiness result for the local single-user startup MVP.

    This deliberately does not convert repository engineering completion into a
    production, commercial or scientific claim. A local startup MVP may be ready
    while protected pilot deployment still needs operator configuration, and a
    guarded single-node pilot may be ready while hosted multi-tenant/HA scope
    remains explicitly unauthorized.
    """

    completion = engineering_completion_report(capabilities)
    checks: list[dict[str, Any]] = []

    engineering_ready = bool(
        completion.get("total_gates", 0)
        and completion.get("passed_gates") == completion.get("total_gates")
        and completion.get("engineering_percent") == 100.0
    )
    checks.append(
        _check(
            "repository_engineering_completion",
            passed=engineering_ready,
            detail=(
                "The existing capability-derived engineering gate surface is complete."
                if engineering_ready
                else "One or more capability-derived repository engineering gates are incomplete."
            ),
            evidence_state=(
                "STARTUP_MVP_ENGINEERING_GATES_COMPLETE"
                if engineering_ready
                else "STARTUP_MVP_ENGINEERING_GATES_INCOMPLETE"
            ),
            source="engineering_completion",
        )
    )

    feature_check, unsafe_features = _feature_policy_check(feature_registry)
    checks.append(feature_check)

    api_contract_ready = _is_sha256(api_contract_sha256) and isinstance(api_route_count, int) and api_route_count > 0
    checks.append(
        _check(
            "api_contract_identity",
            passed=api_contract_ready,
            detail=(
                f"Versioned API route contract is fingerprinted across {api_route_count} routes."
                if api_contract_ready
                else "Versioned API route contract fingerprint is unavailable or malformed."
            ),
            evidence_state=(
                "STARTUP_MVP_API_CONTRACT_IDENTIFIED"
                if api_contract_ready
                else "STARTUP_MVP_API_CONTRACT_MISSING"
            ),
            source="api_contract",
        )
    )

    capability_map = pilot_capabilities.get("capabilities")
    pilot_capability_values = capability_map if isinstance(capability_map, Mapping) else {}
    missing_pilot_capabilities = [
        capability
        for capability in _REQUIRED_PILOT_CAPABILITIES
        if not str(pilot_capability_values.get(capability, "MISSING")).startswith("IMPLEMENTED_TESTED")
    ]
    pilot_capability_ready = bool(
        pilot_capabilities.get("schema") == "morpheus-startup-pilot-capabilities-v1"
        and pilot_capabilities.get("declared_scope") == "SINGLE_NODE_ENGINEERING_PILOT"
        and pilot_capabilities.get("production_deployment_authorized") is False
        and not missing_pilot_capabilities
    )
    checks.append(
        _check(
            "startup_pilot_capability_integrity",
            passed=pilot_capability_ready,
            detail=(
                "Required single-node startup/pilot hardening capabilities are present and production authorization remains denied."
                if pilot_capability_ready
                else "Required single-node startup/pilot hardening capability evidence is missing or scope was widened unsafely."
            ),
            evidence_state=(
                "STARTUP_MVP_PILOT_CAPABILITIES_PRESENT"
                if pilot_capability_ready
                else "STARTUP_MVP_PILOT_CAPABILITIES_INCOMPLETE"
            ),
            source="pilot_capabilities",
        )
    )

    diagnostic_toolchain = diagnostics.get("toolchain")
    diagnostics_ready = bool(
        str(diagnostics.get("python", "")).strip()
        and str(diagnostics.get("system", "")).strip()
        and diagnostics.get("evidence_state") == "LOCAL_ENVIRONMENT_DIAGNOSTIC"
        and isinstance(diagnostic_toolchain, Mapping)
        and str(diagnostic_toolchain.get("kind", "")).strip()
        and str(diagnostic_toolchain.get("version", "")).strip()
    )
    checks.append(
        _check(
            "local_environment_identity",
            passed=diagnostics_ready,
            detail=(
                "Python, operating-system and native C++ toolchain identities are available."
                if diagnostics_ready
                else "Local runtime/toolchain identity is incomplete; generated-artifact verification cannot be treated as startup-ready."
            ),
            evidence_state=(
                "STARTUP_MVP_LOCAL_ENVIRONMENT_IDENTIFIED"
                if diagnostics_ready
                else "STARTUP_MVP_LOCAL_ENVIRONMENT_INCOMPLETE"
            ),
            source="system_diagnostics",
        )
    )

    raw_pilot_checks = pilot_readiness.get("checks")
    pilot_checks = {
        str(item.get("id")): item
        for item in raw_pilot_checks
        if isinstance(item, Mapping) and item.get("id")
    } if isinstance(raw_pilot_checks, list) else {}
    for check_id in _LOCAL_PILOT_CHECK_IDS:
        inherited = pilot_checks.get(check_id)
        passed = bool(inherited and inherited.get("passed") is True)
        checks.append(
            _check(
                check_id,
                passed=passed,
                detail=(
                    str(inherited.get("detail", "Verified by pilot preflight."))
                    if inherited
                    else "Required pilot-preflight evidence is missing."
                ),
                evidence_state=(
                    str(inherited.get("evidence_state", "STARTUP_MVP_INHERITED_CHECK_PASSED"))
                    if inherited and passed
                    else "STARTUP_MVP_INHERITED_CHECK_BLOCKED"
                ),
                source="pilot_readiness",
            )
        )

    blockers = [item["id"] for item in checks if item["required"] and not item["passed"]]
    passed_count = sum(int(item["passed"]) for item in checks)
    total_count = len(checks)
    startup_mvp_percent = round(100.0 * passed_count / total_count, 1) if total_count else 0.0
    local_ready = not blockers

    raw_pilot_blockers = pilot_readiness.get("blockers")
    pilot_blockers = [str(item) for item in raw_pilot_blockers] if isinstance(raw_pilot_blockers, list) else []
    raw_advisories = pilot_readiness.get("advisories")
    advisories = [str(item) for item in raw_advisories] if isinstance(raw_advisories, list) else []
    pilot_configuration_blockers = [
        item for item in pilot_blockers if item in _PILOT_CONFIGURATION_CHECK_IDS
    ]
    other_pilot_blockers = [
        item
        for item in pilot_blockers
        if item not in _PILOT_CONFIGURATION_CHECK_IDS and item not in _LOCAL_PILOT_CHECK_IDS
    ]
    pilot_ready = bool(local_ready and pilot_readiness.get("ready") is True)

    if not local_ready:
        state = "STARTUP_MVP_NOT_READY"
    elif pilot_ready:
        state = "STARTUP_MVP_READY_GUARDED_SINGLE_NODE_PILOT"
    elif other_pilot_blockers:
        state = "STARTUP_MVP_READY_LOCAL_PILOT_HARDENING_PENDING"
    else:
        state = "STARTUP_MVP_READY_LOCAL_PILOT_CONFIGURATION_PENDING"

    sanitized_toolchain = None
    if isinstance(diagnostic_toolchain, Mapping):
        sanitized_toolchain = {
            "kind": str(diagnostic_toolchain.get("kind", "")),
            "version": str(diagnostic_toolchain.get("version", "")),
        }

    core = {
        "schema": SCHEMA,
        "ready": local_ready,
        "state": state,
        "startup_mvp_percent": startup_mvp_percent,
        "passed_checks": passed_count,
        "total_checks": total_count,
        "checks": checks,
        "blockers": blockers,
        "pilot_ready": pilot_ready,
        "pilot_blockers": pilot_blockers,
        "pilot_configuration_blockers": pilot_configuration_blockers,
        "pilot_other_blockers": other_pilot_blockers,
        "advisories": advisories,
        "engineering_completion": {
            "schema": completion.get("schema"),
            "passed_gates": completion.get("passed_gates"),
            "total_gates": completion.get("total_gates"),
            "percent": completion.get("engineering_percent"),
        },
        "compatibility": {
            "feature_registry_sha256": feature_registry.get("sha256"),
            "api_contract_sha256": api_contract_sha256,
            "api_route_count": api_route_count,
        },
        "environment": {
            "python": str(diagnostics.get("python", "")),
            "system": str(diagnostics.get("system", "")),
            "machine": str(diagnostics.get("machine", "")),
            "toolchain": sanitized_toolchain,
        },
        "scope": {
            "readiness_target": "LOCAL_SINGLE_USER_STARTUP_MVP",
            "pilot_target": "GUARDED_SINGLE_NODE_ENGINEERING_PILOT",
            "hosted_multi_tenant_target": "OUT_OF_SCOPE_NOT_AUTHORIZED",
            "production_deployment_authorized": False,
            "automatic_control_allowed": False,
        },
        "unsafe_feature_policy_findings": unsafe_features,
        "missing_required_pilot_capabilities": missing_pilot_capabilities,
        "excluded_external_outcomes": [
            "customer traction or commercial validation",
            "independent benchmark or scientific validation",
            "external production deployment",
            "high-availability or multi-region operation",
            "multi-tenant identity and authorization",
            "security or regulatory certification",
            "universal performance superiority",
            "novelty or patentability",
        ],
        "truth_boundaries": [
            "startup_mvp_percent is a deterministic count of explicit local readiness checks in this schema; it is not a commercial, scientific, legal, security-certification or external-production score.",
            "Local startup-MVP readiness is intentionally distinct from guarded pilot deployment readiness; API-key/rate-limit deployment configuration may remain pending while the loopback single-user MVP is usable.",
            "Guarded single-node pilot readiness does not authorize hosted multi-tenancy, HA/distributed deployment, native cross-process hot swap or a production SLA.",
            "Feature-policy, evidence-ledger, idempotency and compatibility checks are fail-closed but do not constitute cryptographic remote attestation or an external security audit.",
            "No readiness state authorizes new automatic control; existing feature-policy authority remains the sole control boundary.",
        ],
    }
    return {**core, "readiness_sha256": _canonical_sha256(core)}
