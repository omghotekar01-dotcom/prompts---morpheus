from __future__ import annotations

import math
from dataclasses import dataclass

from .calibration import CALIBRATIONS
from .catalog import PRIMITIVES
from .models import AccessDistribution, CalibrationProfile, QueryKind, QuerySpec, WorkloadSpec


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


def _measurement(
    primitive_name: str,
    operation: str | QueryKind,
    profile: CalibrationProfile,
):
    primitive = PRIMITIVES[primitive_name]
    return CALIBRATIONS.measurement(
        primitive_name,
        operation,
        profile=profile,
        expected_implementation_id=primitive.implementation_id,
    )


def _source(profile: CalibrationProfile, primitive_name: str) -> str:
    return f"CALIBRATED:{profile.id}:{PRIMITIVES[primitive_name].implementation_id}:n={profile.record_count}"


def _profile_matches_scale(record_count: int, profile: CalibrationProfile) -> bool:
    """Require the empirical anchor to have been measured at this exact scale.

    Earlier revisions scaled a single measured anchor to arbitrary record counts
    using hand-written complexity formulas. That can remain a modeling research
    direction, but it is not calibrated evidence. Until a multi-scale fitted
    model has its own held-out validation, MORPHEUS consumes a profile only at
    the record count it actually measured.
    """

    return record_count == profile.record_count


def estimate_query_latency_us(
    spec: WorkloadSpec,
    query: QuerySpec,
    primitive_name: str,
    *,
    profile: CalibrationProfile | None = None,
) -> ScalarEstimate:
    # Current primitive calibration protocol generates a uniform deterministic
    # query stream. A matching implementation/scale measurement is therefore not
    # evidence for hotspot, sequential or Zipf access. Preserve those semantics
    # in MWS/IR, but fail closed to a high-uncertainty prior until a
    # distribution-aware benchmark protocol supplies matching evidence.
    distribution_is_calibrated = query.distribution.kind == AccessDistribution.UNIFORM
    selected = profile or CALIBRATIONS.active()
    if (
        distribution_is_calibrated
        and selected is not None
        and _profile_matches_scale(spec.record_count, selected)
    ):
        measurement = _measurement(primitive_name, query.kind, selected)
        if measurement is not None:
            measured_us = measurement.ns_per_op / 1000.0
            if measurement.stdev_ns is not None and measurement.ns_per_op > 0:
                empirical_ratio = measurement.stdev_ns / measurement.ns_per_op
                uncertainty = min(max(empirical_ratio * 2.0, 0.08), 0.60)
            else:
                uncertainty = 0.20
            return ScalarEstimate(
                value=measured_us,
                source=_source(selected, primitive_name),
                uncertainty_ratio=uncertainty,
            )

    if not distribution_is_calibrated:
        return ScalarEstimate(
            value=_bootstrap_latency_us(spec, query, primitive_name),
            source=f"BOOTSTRAP_PRIOR_DISTRIBUTION_UNMODELED:{query.distribution.kind.value}",
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
) -> ScalarEstimate:
    selected = profile or CALIBRATIONS.active()
    # An empirical update measurement is only calibrated evidence at the exact
    # record count where it was measured. If the caller cannot provide a scale,
    # fail closed to the bootstrap prior instead of silently consuming an anchor.
    scale_matches = (
        selected is not None
        and record_count is not None
        and _profile_matches_scale(record_count, selected)
    )
    if selected is not None and scale_matches:
        for operation in (QueryKind.UPDATE, QueryKind.INSERT, QueryKind.DELETE):
            measurement = _measurement(primitive_name, operation, selected)
            if measurement is not None:
                return ScalarEstimate(
                    measurement.ns_per_op / 1000.0,
                    _source(selected, primitive_name),
                    0.25,
                )
    return ScalarEstimate(PRIMITIVES[primitive_name].update_latency_us, "BOOTSTRAP_PRIOR", 0.55)
