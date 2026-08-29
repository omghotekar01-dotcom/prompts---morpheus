from __future__ import annotations

import math
from dataclasses import dataclass

from .calibration import CALIBRATIONS
from .catalog import PRIMITIVES
from .models import CalibrationProfile, QueryDistributionSpec, QueryKind, QuerySpec, WorkloadSpec


@dataclass(frozen=True)
class ScalarEstimate:
    value: float
    source: str
    uncertainty_ratio: float


def _bootstrap_latency_us(spec: WorkloadSpec, query: QuerySpec, primitive_name: str) -> float:
    primitive = PRIMITIVES[primitive_name]
    base = primitive.base_latency_us[query.kind]
    n = max(spec.record_count, 2)
    log_factor = max(math.log2(n) / 20.0, 0.25)
    selectivity = query.selectivity if query.selectivity is not None else 0.01

    if primitive_name == "robin_hood_hash":
        return base * (1.0 + 0.02 * log_factor)
    if primitive_name == "ordered_tree":
        if query.kind == QueryKind.RANGE_SCAN:
            return base * log_factor + (selectivity * n) * 0.00004
        return base * log_factor
    if primitive_name == "sorted_array":
        if query.kind == QueryKind.RANGE_SCAN:
            return base * log_factor + (selectivity * n) * 0.000025
        return base * log_factor
    if primitive_name == "radix_trie":
        prefix_factor = max((query.prefix_length or 4) / 4.0, 0.5)
        return base * prefix_factor
    if primitive_name == "bitmap":
        return base + (selectivity * n) * 0.000012
    if primitive_name == "csr_graph":
        return base * max(math.sqrt(n) / 300.0, 1.0)
    return base


def _distribution_signature(distribution: QueryDistributionSpec) -> str:
    if distribution.kind.value == "zipf":
        return f"zipf(theta={distribution.zipf_theta:g})"
    if distribution.kind.value == "hotspot":
        return (
            f"hotspot(f={distribution.hotspot_fraction:g},"
            f"p={distribution.hotspot_probability:g})"
        )
    return distribution.kind.value


def _measurement(
    primitive_name: str,
    operation: str | QueryKind,
    profile: CalibrationProfile,
    *,
    expected_distribution: QueryDistributionSpec | None = None,
    require_distribution_identity: bool = False,
):
    primitive = PRIMITIVES[primitive_name]
    return CALIBRATIONS.measurement(
        primitive_name,
        operation,
        profile=profile,
        expected_implementation_id=primitive.implementation_id,
        expected_distribution=expected_distribution,
        require_distribution_identity=require_distribution_identity,
    )


def _source(
    profile: CalibrationProfile,
    primitive_name: str,
    *,
    distribution: QueryDistributionSpec | None = None,
) -> str:
    base = f"CALIBRATED:{profile.id}:{PRIMITIVES[primitive_name].implementation_id}:n={profile.record_count}"
    return f"{base}:dist={_distribution_signature(distribution)}" if distribution is not None else base


def _profile_matches_scale(record_count: int, profile: CalibrationProfile) -> bool:
    """Require empirical anchors to have been measured at this exact scale.

    MORPHEUS has an offline interpolation evaluator, but interpolation has not
    been promoted into the optimizer. Until that separate model passes held-out
    acceptance, the production cost path consumes empirical anchors only at the
    record count they actually measured.
    """

    return record_count == profile.record_count


def _measurement_uncertainty(measurement, *, floor: float = 0.08, ceiling: float = 0.60) -> float:
    if measurement.stdev_ns is not None and measurement.ns_per_op > 0:
        empirical_ratio = measurement.stdev_ns / measurement.ns_per_op
        return min(max(empirical_ratio * 2.0, floor), ceiling)
    return max(floor, 0.20)


def estimate_query_latency_us(
    spec: WorkloadSpec,
    query: QuerySpec,
    primitive_name: str,
    *,
    profile: CalibrationProfile | None = None,
) -> ScalarEstimate:
    selected = profile or CALIBRATIONS.active()
    if selected is not None and _profile_matches_scale(spec.record_count, selected):
        measurement = _measurement(
            primitive_name,
            query.kind,
            selected,
            expected_distribution=query.distribution,
            require_distribution_identity=True,
        )
        if measurement is not None:
            return ScalarEstimate(
                value=measurement.ns_per_op / 1000.0,
                source=_source(selected, primitive_name, distribution=query.distribution),
                uncertainty_ratio=_measurement_uncertainty(measurement),
            )

    # The workload language may describe a distribution even when no empirical
    # anchor matches it. Preserve the semantic distinction in the evidence state
    # instead of quietly borrowing a uniform or differently-parameterized sample.
    if query.distribution.kind.value != "uniform":
        return ScalarEstimate(
            value=_bootstrap_latency_us(spec, query, primitive_name),
            source=f"BOOTSTRAP_PRIOR_DISTRIBUTION_UNMODELED:{_distribution_signature(query.distribution)}",
            uncertainty_ratio=0.80,
        )

    return ScalarEstimate(
        value=_bootstrap_latency_us(spec, query, primitive_name),
        source="BOOTSTRAP_PRIOR",
        uncertainty_ratio=0.50,
    )


def estimate_build_ms(
    spec: WorkloadSpec,
    primitive_name: str,
    *,
    profile: CalibrationProfile | None = None,
) -> ScalarEstimate:
    selected = profile or CALIBRATIONS.active()
    if selected is not None and _profile_matches_scale(spec.record_count, selected):
        measurement = _measurement(primitive_name, "build", selected)
        if measurement is not None:
            total_ms = measurement.ns_per_op * spec.record_count / 1_000_000.0
            return ScalarEstimate(total_ms, _source(selected, primitive_name), 0.25)

    primitive = PRIMITIVES[primitive_name]
    total_ms = primitive.build_ns_per_record * spec.record_count / 1_000_000.0
    return ScalarEstimate(total_ms, "BOOTSTRAP_PRIOR", 0.55)


def estimate_update_us(
    primitive_name: str,
    *,
    profile: CalibrationProfile | None = None,
    record_count: int | None = None,
    distribution: QueryDistributionSpec | None = None,
    operation: QueryKind | None = None,
) -> ScalarEstimate:
    """Estimate one physical-index mutation under an optional exact access pattern.

    Empirical mutation evidence is consumed only when the caller supplies an
    exact distribution and exact mutation operation. If operation is omitted,
    this legacy-compatible helper may look across mutation operation labels, but
    the synthesis path always supplies the declared QueryKind and therefore
    cannot borrow an UPDATE sample for INSERT or DELETE traffic.
    """

    selected = profile or CALIBRATIONS.active()
    scale_matches = (
        selected is not None
        and record_count is not None
        and _profile_matches_scale(record_count, selected)
    )
    if selected is not None and scale_matches and distribution is not None:
        operations = (
            (operation,)
            if operation is not None
            else (QueryKind.UPDATE, QueryKind.INSERT, QueryKind.DELETE)
        )
        for operation_kind in operations:
            if operation_kind not in {QueryKind.UPDATE, QueryKind.INSERT, QueryKind.DELETE}:
                continue
            measurement = _measurement(
                primitive_name,
                operation_kind,
                selected,
                expected_distribution=distribution,
                require_distribution_identity=True,
            )
            if measurement is not None:
                return ScalarEstimate(
                    measurement.ns_per_op / 1000.0,
                    _source(selected, primitive_name, distribution=distribution),
                    _measurement_uncertainty(measurement, floor=0.10, ceiling=0.65),
                )
    return ScalarEstimate(PRIMITIVES[primitive_name].update_latency_us, "BOOTSTRAP_PRIOR", 0.55)


def estimate_update_mix_us(
    spec: WorkloadSpec,
    primitive_name: str,
    *,
    profile: CalibrationProfile | None = None,
) -> ScalarEstimate:
    """Estimate physical-index maintenance over declared mutation operations.

    If the workload contains explicit INSERT/UPDATE/DELETE operations, MORPHEUS
    combines their exact operation+distribution-bound estimates by declared
    weights. If updates are represented only by `constraints.update_rate`, the
    access pattern is unknown and the engine intentionally stays on the
    bootstrap prior rather than manufacturing locality evidence.
    """

    mutations = [
        query
        for query in spec.queries
        if query.kind in {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}
    ]
    if not mutations:
        return ScalarEstimate(PRIMITIVES[primitive_name].update_latency_us, "BOOTSTRAP_PRIOR", 0.55)

    estimates = [
        (
            query.weight,
            estimate_update_us(
                primitive_name,
                profile=profile,
                record_count=spec.record_count,
                distribution=query.distribution,
                operation=query.kind,
            ),
        )
        for query in mutations
    ]
    total_weight = sum(weight for weight, _ in estimates)
    value = sum(weight * estimate.value for weight, estimate in estimates) / max(total_weight, 1e-12)
    uncertainty = max(estimate.uncertainty_ratio for _, estimate in estimates)
    sources = sorted({estimate.source for _, estimate in estimates})
    if all(source.startswith("CALIBRATED:") for source in sources):
        source = "CALIBRATED:MUTATION_MIX:" + ",".join(sources)
    elif any(source.startswith("CALIBRATED:") for source in sources):
        source = "MIXED_CALIBRATED_BOOTSTRAP_MUTATION:" + ",".join(sources)
    else:
        source = "BOOTSTRAP_PRIOR"
    return ScalarEstimate(value=value, source=source, uncertainty_ratio=uncertainty)
