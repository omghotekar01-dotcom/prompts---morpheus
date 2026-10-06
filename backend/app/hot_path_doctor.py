from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .active_measurement import assess_decision_confidence
from .catalog import PRIMITIVES
from .models import CandidateResult, QueryKind, SynthesisResult, WorkloadSpec


@dataclass(frozen=True)
class CurrentStructureProfile:
    id: str
    label: str
    capabilities: frozenset[QueryKind]
    caveat: str


CURRENT_STRUCTURES: dict[str, CurrentStructureProfile] = {
    "std_unordered_map": CurrentStructureProfile(
        id="std_unordered_map",
        label="std::unordered_map / hash map",
        capabilities=frozenset(
            {
                QueryKind.POINT_LOOKUP,
                QueryKind.INSERT,
                QueryKind.UPDATE,
                QueryKind.DELETE,
            }
        ),
        caveat="Coverage describes declared operation compatibility only; it is not a measured speed comparison.",
    ),
    "std_map": CurrentStructureProfile(
        id="std_map",
        label="std::map / ordered tree",
        capabilities=frozenset(
            {
                QueryKind.POINT_LOOKUP,
                QueryKind.RANGE_SCAN,
                QueryKind.INSERT,
                QueryKind.UPDATE,
                QueryKind.DELETE,
            }
        ),
        caveat="Coverage describes declared operation compatibility only; implementation constants and cache behavior are not inferred.",
    ),
    "sorted_vector": CurrentStructureProfile(
        id="sorted_vector",
        label="Sorted vector / array index",
        capabilities=frozenset({QueryKind.POINT_LOOKUP, QueryKind.RANGE_SCAN}),
        caveat="Read-route compatibility does not imply acceptable mutation cost; production update behavior requires measurement.",
    ),
    "linear_scan": CurrentStructureProfile(
        id="linear_scan",
        label="Vector/list scan",
        capabilities=frozenset(
            {
                QueryKind.POINT_LOOKUP,
                QueryKind.RANGE_SCAN,
                QueryKind.FILTER,
                QueryKind.PREFIX_SEARCH,
            }
        ),
        caveat="Generic scan semantics can express several reads, but this compatibility score intentionally makes no complexity or latency claim.",
    ),
    "custom_or_unknown": CurrentStructureProfile(
        id="custom_or_unknown",
        label="Custom / unknown implementation",
        capabilities=frozenset(),
        caveat="MORPHEUS cannot infer capability or performance for an unspecified current implementation.",
    ),
}


def _normalized_query_weights(spec: WorkloadSpec) -> list[float]:
    total = sum(query.weight for query in spec.queries)
    if total <= 0:
        return [0.0 for _ in spec.queries]
    return [query.weight / total for query in spec.queries]


def _workload_fingerprint(spec: WorkloadSpec) -> dict[str, Any]:
    weights = _normalized_query_weights(spec)
    operation_mix: dict[str, float] = {}
    distribution_mix: dict[str, float] = {}
    field_pressure: dict[str, float] = {}

    for weight, query in zip(weights, spec.queries, strict=True):
        operation_mix[query.kind.value] = operation_mix.get(query.kind.value, 0.0) + weight
        distribution_mix[query.distribution.kind.value] = (
            distribution_mix.get(query.distribution.kind.value, 0.0) + weight
        )
        if query.field:
            field_pressure[query.field] = field_pressure.get(query.field, 0.0) + weight

    dominant_operation = max(operation_mix, key=operation_mix.get) if operation_mix else None
    dominant_distribution = max(distribution_mix, key=distribution_mix.get) if distribution_mix else None
    dominant_field = max(field_pressure, key=field_pressure.get) if field_pressure else None
    mutation_weight = sum(
        weight
        for weight, query in zip(weights, spec.queries, strict=True)
        if query.kind in {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}
    )

    return {
        "record_count": spec.record_count,
        "query_routes": len(spec.queries),
        "operation_mix": {key: round(value, 6) for key, value in sorted(operation_mix.items())},
        "distribution_mix": {key: round(value, 6) for key, value in sorted(distribution_mix.items())},
        "field_pressure": {key: round(value, 6) for key, value in sorted(field_pressure.items())},
        "dominant_operation": dominant_operation,
        "dominant_distribution": dominant_distribution,
        "dominant_field": dominant_field,
        "mutation_weight_ratio": round(mutation_weight, 6),
        "memory_constraint_mb": spec.constraints.memory_mb,
        "p99_constraint_us": spec.constraints.p99_latency_us,
        "declared_update_rate": spec.constraints.update_rate,
    }


def _current_structure_assessment(
    spec: WorkloadSpec,
    current_structure: str,
) -> dict[str, Any]:
    profile = CURRENT_STRUCTURES[current_structure]
    if current_structure == "custom_or_unknown":
        return {
            "id": profile.id,
            "label": profile.label,
            "supported_weight_ratio": None,
            "unsupported_weight_ratio": None,
            "unsupported_query_indexes": list(range(len(spec.queries))),
            "unsupported_operations": sorted({query.kind.value for query in spec.queries}),
            "assessment": "CURRENT_IMPLEMENTATION_UNKNOWN",
            "caveat": profile.caveat,
            "evidence_state": "USER_DECLARED_CURRENT_STRUCTURE_NOT_BENCHMARKED",
        }

    weights = _normalized_query_weights(spec)
    supported = 0.0
    unsupported_indexes: list[int] = []
    unsupported_operations: set[str] = set()
    for index, (weight, query) in enumerate(zip(weights, spec.queries, strict=True)):
        if query.kind in profile.capabilities:
            supported += weight
        else:
            unsupported_indexes.append(index)
            unsupported_operations.add(query.kind.value)

    supported = min(1.0, max(0.0, supported))
    unsupported = 1.0 - supported
    assessment = (
        "DECLARED_WORKLOAD_FULLY_COVERED_BY_CURRENT_STRUCTURE_SEMANTICS"
        if not unsupported_indexes
        else "DECLARED_WORKLOAD_HAS_SPECIALIZATION_GAPS"
    )
    return {
        "id": profile.id,
        "label": profile.label,
        "supported_weight_ratio": round(supported, 6),
        "unsupported_weight_ratio": round(unsupported, 6),
        "unsupported_query_indexes": unsupported_indexes,
        "unsupported_operations": sorted(unsupported_operations),
        "assessment": assessment,
        "caveat": profile.caveat,
        "evidence_state": "DETERMINISTIC_DECLARED_CAPABILITY_COVERAGE_NOT_PERFORMANCE_EVIDENCE",
    }


def _winner_routes(candidate: CandidateResult) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for assignment in candidate.assignments:
        primitive = PRIMITIVES[assignment.primitive]
        routes.append(
            {
                "query_index": assignment.query_index,
                "query_kind": assignment.query_kind.value,
                "field": assignment.field,
                "primitive": primitive.name,
                "primitive_label": primitive.display_name,
                "implementation_id": primitive.implementation_id,
            }
        )
    return routes


def _migration_playbook(
    spec: WorkloadSpec,
    result: SynthesisResult,
    confidence: dict[str, Any],
) -> list[dict[str, str]]:
    winner = result.winner
    if winner is None:
        return [
            {
                "step": "resolve_constraints",
                "title": "Resolve the infeasible workload",
                "action": "Review hard memory/latency/build constraints or unsupported routes before generating a migration.",
                "gate": "NO_FEASIBLE_CANDIDATE",
            }
        ]

    read_only = all(
        query.kind not in {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}
        for query in spec.queries
    )
    if confidence["decision_confident_under_interval_heuristic"]:
        measurement_action = "Benchmark the selected generated candidate on the target machine."
    else:
        measurement_action = (
            "Benchmark the ambiguity set on the target machine before choosing a winner; modeled intervals overlap."
        )

    steps = [
        {
            "step": "measure",
            "title": "Turn the model into machine-local evidence",
            "action": measurement_action,
            "gate": "LOCAL_MEASUREMENT_REQUIRED_BEFORE_PERFORMANCE_CLAIM",
        },
        {
            "step": "verify",
            "title": "Compile and behavior-verify generated C++20",
            "action": "Run full artifact verification and keep the source/configuration/workload hashes with the result.",
            "gate": "COMPILE_AND_CORRECTNESS_VERIFICATION_REQUIRED",
        },
        {
            "step": "shadow",
            "title": "Build beside the current implementation",
            "action": (
                "Create the replacement as a shadow structure and feed the same bounded input without switching production ownership."
            ),
            "gate": "NO_LIVE_PROCESS_SWAP",
        },
        {
            "step": "compare",
            "title": "Compare correctness before performance",
            "action": (
                "Run dual-read or replay validation on representative traffic and investigate any result mismatch before considering cutover."
            ),
            "gate": "CORRECTNESS_BEFORE_CUTOVER",
        },
        {
            "step": "cutover",
            "title": "Use an explicit, reversible deployment",
            "action": (
                "Apply the generated integration manually behind a feature flag or controlled release and preserve the old structure as the rollback path."
            ),
            "gate": "HUMAN_AUTHORIZED_DEPLOYMENT_ONLY",
        },
    ]
    if not read_only:
        steps[0]["action"] += (
            " Mutation routes are declared, so the current query-latency measurement bridge cannot by itself validate insert/update/delete behavior."
        )
    return steps


def diagnose_hot_path(
    spec: WorkloadSpec,
    result: SynthesisResult,
    *,
    current_structure: str,
) -> dict[str, Any]:
    if current_structure not in CURRENT_STRUCTURES:
        raise ValueError(f"unsupported current_structure: {current_structure}")

    current = _current_structure_assessment(spec, current_structure)
    fingerprint = _workload_fingerprint(spec)

    if result.winner is None:
        return {
            "schema": "morpheus-hot-path-doctor-v1",
            "problem": {
                "category": "APPLICATION_HOT_PATH_DATA_STRUCTURE_SELECTION",
                "summary": (
                    "The declared hot path has no feasible MORPHEUS candidate under the current hard constraints."
                ),
            },
            "workload": fingerprint,
            "current_structure": current,
            "recommendation": None,
            "confidence": None,
            "migration_playbook": _migration_playbook(spec, result, {
                "decision_confident_under_interval_heuristic": False
            }),
            "launch_state": "BLOCKED_NO_FEASIBLE_CANDIDATE",
            "truth_boundary": (
                "This diagnosis is deterministic repository-local reasoning over the supplied MWS. "
                "No performance improvement, production impact, or deployment success is claimed."
            ),
        }

    assessment = assess_decision_confidence(result)
    confidence = assessment.as_dict()
    winner = result.winner
    recommendation = {
        "candidate_id": winner.id,
        "primitives": [
            {
                "id": name,
                "label": PRIMITIVES[name].display_name,
                "implementation_id": PRIMITIVES[name].implementation_id,
            }
            for name in winner.unique_primitives
        ],
        "routes": _winner_routes(winner),
        "predicted_latency_us": winner.predicted_latency_us,
        "predicted_memory_mb": winner.predicted_memory_mb,
        "predicted_build_ms": winner.predicted_build_ms,
        "predicted_update_us": winner.predicted_update_us,
        "prediction_source": winner.prediction_source,
        "evidence_state": result.evidence_state,
        "warnings": list(result.warnings),
    }

    next_gate = (
        "MEASURE_AMBIGUOUS_FINALISTS"
        if not assessment.decision_confident_under_interval_heuristic
        else "MEASURE_GENERATED_WINNER"
    )
    if result.evidence_state == "CALIBRATED_MODEL_NOT_END_TO_END_MEASURED":
        next_gate += "_CALIBRATED_MODEL_STILL_NEEDS_END_TO_END_MEASUREMENT"

    unsupported_ratio = current.get("unsupported_weight_ratio")
    if isinstance(unsupported_ratio, float) and unsupported_ratio > 0:
        problem_summary = (
            f"The declared current structure does not natively cover {unsupported_ratio:.1%} "
            "of normalized workload weight under this capability model."
        )
    elif current_structure == "custom_or_unknown":
        problem_summary = (
            "The current implementation is unspecified, so MORPHEUS cannot truthfully compare its capability or performance."
        )
    else:
        problem_summary = (
            "The current structure covers the declared operation classes, but specialization and target-machine performance remain open questions."
        )

    return {
        "schema": "morpheus-hot-path-doctor-v1",
        "problem": {
            "category": "APPLICATION_HOT_PATH_DATA_STRUCTURE_SELECTION",
            "summary": problem_summary,
            "why_it_matters": (
                "Application containers are often chosen once while workload shape, skew, scale, memory budget and latency targets evolve. "
                "MORPHEUS turns that choice into an explicit workload-to-design-to-measurement workflow."
            ),
        },
        "workload": fingerprint,
        "current_structure": current,
        "recommendation": recommendation,
        "confidence": confidence,
        "migration_playbook": _migration_playbook(spec, result, confidence),
        "next_gate": next_gate,
        "launch_state": "RECOMMENDATION_REQUIRES_LOCAL_MEASUREMENT_AND_VERIFICATION",
        "automatic_control_allowed": False,
        "truth_boundary": (
            "Current-structure coverage is semantic capability coverage, not a benchmark. "
            "Winner costs are predictions unless the evidence state explicitly says otherwise. "
            "The doctor does not claim speedup, production impact, universal superiority, or permission to change a live system. "
            "Local measurement, generated-artifact verification, correctness comparison and an explicit human-controlled deployment remain separate gates."
        ),
    }


def hot_path_doctor_options() -> dict[str, Any]:
    return {
        "schema": "morpheus-hot-path-doctor-options-v1",
        "current_structures": [
            {
                "id": profile.id,
                "label": profile.label,
                "capabilities": sorted(item.value for item in profile.capabilities),
                "caveat": profile.caveat,
            }
            for profile in CURRENT_STRUCTURES.values()
        ],
        "problem": (
            "Choose and safely migrate application-level in-memory data structures from explicit workload evidence rather than folklore."
        ),
        "automatic_control_allowed": False,
    }
