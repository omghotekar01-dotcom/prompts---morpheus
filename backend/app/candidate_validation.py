from __future__ import annotations

from dataclasses import dataclass

from .candidate_benchmark import CandidateBenchmarkResult
from .models import CandidateResult, QueryKind, WorkloadSpec


_MUTATIONS = {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}


@dataclass(frozen=True)
class CandidateValidationPoint:
    workload_id: str
    candidate_id: str
    predicted_query_latency_us: float
    measured_weighted_query_latency_us: float
    absolute_error_us: float
    relative_error: float | None
    benchmark_configuration_ir_hash: str
    evidence_state: str = "CANDIDATE_PREDICTION_COMPARED_TO_LOCAL_END_TO_END_MEASUREMENT"

    def as_dict(self) -> dict[str, object]:
        return {
            "workload_id": self.workload_id,
            "candidate_id": self.candidate_id,
            "predicted_query_latency_us": self.predicted_query_latency_us,
            "measured_weighted_query_latency_us": self.measured_weighted_query_latency_us,
            "absolute_error_us": self.absolute_error_us,
            "relative_error": self.relative_error,
            "benchmark_configuration_ir_hash": self.benchmark_configuration_ir_hash,
            "evidence_state": self.evidence_state,
            "truth_boundary": (
                "This point compares the modeled aggregate query latency with a local generated-candidate benchmark under its declared synthetic workload. "
                "It does not establish cross-machine model accuracy or publication-grade generalization."
            ),
        }


def measured_weighted_query_latency_us(
    spec: WorkloadSpec,
    benchmark: CandidateBenchmarkResult,
) -> float:
    """Aggregate measured read-route medians using the MWS query weights.

    The current candidate harness has a real end-to-end `update_record` path but
    not separate INSERT/UPDATE/DELETE operation semantics. To avoid mixing
    unlike measurements, this bridge deliberately rejects mutation-declaring
    workloads until a mutation-specific validation protocol is implemented.
    """

    mutations = [index for index, query in enumerate(spec.queries) if query.kind in _MUTATIONS]
    if mutations:
        raise ValueError(
            f"candidate query-latency validation currently requires read-only MWS; mutation query indexes: {mutations}"
        )
    if not benchmark.success:
        raise ValueError("candidate benchmark must succeed before measurement aggregation")

    by_name = {str(item.get("name")): item for item in benchmark.measurements}
    weighted = 0.0
    total_weight = 0.0
    for index, query in enumerate(spec.queries):
        item = by_name.get(f"query_{index}")
        if item is None:
            raise ValueError(f"benchmark is missing query_{index} measurement")
        try:
            median_ns = float(item["median_ns"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"benchmark query_{index} has invalid median_ns") from exc
        if median_ns < 0:
            raise ValueError(f"benchmark query_{index} median_ns cannot be negative")
        weighted += (median_ns / 1000.0) * query.weight
        total_weight += query.weight
    if total_weight <= 0:
        raise ValueError("workload query weights must have positive total")
    return weighted / total_weight


def build_candidate_validation_point(
    spec: WorkloadSpec,
    candidate: CandidateResult,
    benchmark: CandidateBenchmarkResult,
    *,
    workload_id: str | None = None,
) -> CandidateValidationPoint:
    if benchmark.candidate_id != candidate.id:
        raise ValueError("benchmark candidate_id does not match modeled candidate")
    measured = measured_weighted_query_latency_us(spec, benchmark)
    predicted = candidate.predicted_latency_us
    absolute_error = abs(predicted - measured)
    relative_error = absolute_error / abs(measured) if measured != 0 else None
    return CandidateValidationPoint(
        workload_id=workload_id or spec.name,
        candidate_id=candidate.id,
        predicted_query_latency_us=predicted,
        measured_weighted_query_latency_us=measured,
        absolute_error_us=absolute_error,
        relative_error=relative_error,
        benchmark_configuration_ir_hash=benchmark.configuration_ir_hash,
    )
