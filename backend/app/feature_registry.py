from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable


FEATURE_REGISTRY_SCHEMA = "morpheus-feature-registry-v1"


class FeatureMaturity(str, Enum):
    STABLE = "stable"
    GUARDED = "guarded"
    RESEARCH = "research"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class FeatureDefinition:
    id: str
    version: str
    maturity: FeatureMaturity
    default_enabled: bool
    automatic_control_allowed: bool
    dependencies: tuple[str, ...]
    update_policy: str
    truth_boundary: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["maturity"] = self.maturity.value
        payload["dependencies"] = list(self.dependencies)
        return payload


_FEATURES: tuple[FeatureDefinition, ...] = (
    FeatureDefinition(
        id="startup_readiness_gate",
        version="1",
        maturity=FeatureMaturity.STABLE,
        default_enabled=True,
        automatic_control_allowed=False,
        dependencies=(),
        update_policy="Backward-compatible UI/readiness changes require frontend build and startup contract validation.",
        truth_boundary="Startup readiness reports service availability; it does not certify benchmark or research validity.",
    ),
    FeatureDefinition(
        id="root_ui_error_boundary",
        version="1",
        maturity=FeatureMaturity.STABLE,
        default_enabled=True,
        automatic_control_allowed=False,
        dependencies=("startup_readiness_gate",),
        update_policy="Recovery behavior may expand, but must never mutate engine state implicitly.",
        truth_boundary="The boundary isolates React render failures only; it is not a backend or generated-code recovery mechanism.",
    ),
    FeatureDefinition(
        id="workload_ir_v2_distribution_semantics",
        version="2",
        maturity=FeatureMaturity.STABLE,
        default_enabled=True,
        automatic_control_allowed=False,
        dependencies=(),
        update_policy="Semantic additions require a new WorkloadIR version or an explicitly backward-compatible field.",
        truth_boundary="Typed distribution semantics describe workload intent; they are not performance measurements.",
    ),
    FeatureDefinition(
        id="generated_candidate_measurement",
        version="1",
        maturity=FeatureMaturity.GUARDED,
        default_enabled=True,
        automatic_control_allowed=False,
        dependencies=("workload_ir_v2_distribution_semantics",),
        update_policy="Measurement protocol changes must version evidence schemas and preserve prior readers.",
        truth_boundary="Generated-candidate measurements are machine-local evidence unless a controlled campaign says otherwise.",
    ),
    FeatureDefinition(
        id="runtime_declared_distribution_drift",
        version="1",
        maturity=FeatureMaturity.GUARDED,
        default_enabled=True,
        automatic_control_allowed=True,
        dependencies=("workload_ir_v2_distribution_semantics",),
        update_policy="Threshold/control changes require runtime regression tests, hysteresis checks and rollback invariants.",
        truth_boundary="Only explicitly supplied distribution telemetry may influence this control signal; inferred trace labels are excluded.",
    ),
    FeatureDefinition(
        id="trace_distribution_classifier",
        version="1",
        maturity=FeatureMaturity.RESEARCH,
        default_enabled=False,
        automatic_control_allowed=False,
        dependencies=("workload_ir_v2_distribution_semantics",),
        update_policy="Promotion requires independent real-trace validation, threshold calibration and explicit registry revision.",
        truth_boundary="Synthetic/finite-trace classification remains descriptive research evidence and cannot authorize runtime switching.",
    ),
    FeatureDefinition(
        id="trace_phase_detection",
        version="1",
        maturity=FeatureMaturity.RESEARCH,
        default_enabled=False,
        automatic_control_allowed=False,
        dependencies=("trace_distribution_classifier",),
        update_policy="Promotion requires statistically calibrated online change-point validation and false-positive analysis.",
        truth_boundary="Rolling phase candidates are descriptive; they are not calibrated online change points.",
    ),
    FeatureDefinition(
        id="local_in_process_dataplane_swap",
        version="1",
        maturity=FeatureMaturity.GUARDED,
        default_enabled=True,
        automatic_control_allowed=True,
        dependencies=("generated_candidate_measurement",),
        update_policy="Publication/rollback semantics require concurrency, health-gate and exact-generation tests on every change.",
        truth_boundary="This is a local in-process routing/swap mechanism, not native cross-process hot replacement.",
    ),
    FeatureDefinition(
        id="native_cross_process_hot_swap",
        version="0",
        maturity=FeatureMaturity.BLOCKED,
        default_enabled=False,
        automatic_control_allowed=False,
        dependencies=("local_in_process_dataplane_swap",),
        update_policy="Do not enable until process isolation, ABI compatibility, migration, health validation and rollback are demonstrated.",
        truth_boundary="Native cross-process hot swap is not implemented and must remain fail-closed.",
    ),
)


def feature_registry() -> tuple[FeatureDefinition, ...]:
    return _FEATURES


def validate_feature_registry(features: Iterable[FeatureDefinition] | None = None) -> None:
    items = tuple(features if features is not None else _FEATURES)
    by_id = {item.id: item for item in items}
    if len(by_id) != len(items):
        raise ValueError("feature registry contains duplicate ids")
    for item in items:
        if not item.id or not item.version:
            raise ValueError("feature id/version must be non-empty")
        if item.maturity in {FeatureMaturity.RESEARCH, FeatureMaturity.BLOCKED} and item.automatic_control_allowed:
            raise ValueError(f"{item.id}: research/blocked features cannot allow automatic control")
        if item.maturity == FeatureMaturity.BLOCKED and item.default_enabled:
            raise ValueError(f"{item.id}: blocked features cannot be enabled by default")
        for dependency in item.dependencies:
            if dependency not in by_id:
                raise ValueError(f"{item.id}: unknown dependency {dependency}")
            if dependency == item.id:
                raise ValueError(f"{item.id}: feature cannot depend on itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(feature_id: str) -> None:
        if feature_id in visited:
            return
        if feature_id in visiting:
            raise ValueError(f"feature dependency cycle detected at {feature_id}")
        visiting.add(feature_id)
        for dependency in by_id[feature_id].dependencies:
            visit(dependency)
        visiting.remove(feature_id)
        visited.add(feature_id)

    for feature_id in by_id:
        visit(feature_id)


def registry_payload() -> dict[str, object]:
    validate_feature_registry()
    return {
        "schema": FEATURE_REGISTRY_SCHEMA,
        "features": [item.as_dict() for item in _FEATURES],
        "truth_boundary": (
            "Feature availability is versioned independently from marketing readiness. "
            "Research or blocked features remain fail-closed for automatic control."
        ),
    }


def evaluate_feature_activation(
    requested_features: Iterable[str],
    *,
    automatic_control: bool = False,
) -> dict[str, object]:
    """Evaluate a feature request without mutating runtime state.

    Dependency availability and decision authority are different concerns. A
    control feature may depend on stable parsing/measurement infrastructure that
    does not itself make a control decision. Therefore every expanded dependency
    must be non-BLOCKED, while `automatic_control_allowed` is required only for
    features the caller explicitly asks to use as automatic-control behavior.
    """

    validate_feature_registry()
    requested = tuple(requested_features)
    if not requested:
        raise ValueError("at least one feature must be requested")
    if len(set(requested)) != len(requested):
        raise ValueError("duplicate requested feature")

    by_id = {item.id: item for item in _FEATURES}
    unknown = sorted(set(requested) - set(by_id))
    if unknown:
        raise ValueError(f"unknown features: {', '.join(unknown)}")

    expanded: set[str] = set()

    def include(feature_id: str) -> None:
        if feature_id in expanded:
            return
        for dependency in by_id[feature_id].dependencies:
            include(dependency)
        expanded.add(feature_id)

    for feature_id in requested:
        include(feature_id)

    blockers: list[dict[str, str]] = []
    for feature_id in sorted(expanded):
        feature = by_id[feature_id]
        if feature.maturity == FeatureMaturity.BLOCKED:
            blockers.append({"feature": feature_id, "reason": "feature maturity is blocked"})

    if automatic_control:
        for feature_id in requested:
            feature = by_id[feature_id]
            if not feature.automatic_control_allowed:
                blockers.append({"feature": feature_id, "reason": "automatic control is not authorized"})

    return {
        "schema": "morpheus-feature-activation-evaluation-v1",
        "requested_features": list(requested),
        "expanded_features": sorted(expanded),
        "automatic_control_requested": automatic_control,
        "allowed": not blockers,
        "decision": "ALLOW" if not blockers else "DENY_FAIL_CLOSED",
        "blockers": blockers,
        "truth_boundary": (
            "Dependencies must be available and non-blocked; only explicitly requested control behaviors require automatic-control authority. "
            "This endpoint evaluates policy only and never mutates runtime feature state."
        ),
    }
