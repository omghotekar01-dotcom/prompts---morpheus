from __future__ import annotations

from app.candidate_benchmark import CandidateBenchmarkResult
from app.candidate_validation import build_candidate_validation_point, measured_weighted_query_latency_us
from app.engine import synthesize
from app.parser import parse_workload_text


SPEC = parse_workload_text(
    """
version: mws-0.1
name: validation_bridge
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
  - name: age
    type: uint32
    cardinality: 80
queries:
  - kind: point_lookup
    field: id
    weight: 0.75
  - kind: range_scan
    field: age
    weight: 0.25
    selectivity: 0.1
""".strip()
)


def _benchmark(candidate_id: str, configuration_hash: str = "b" * 64) -> CandidateBenchmarkResult:
    return CandidateBenchmarkResult(
        success=True,
        evidence_state="MEASURED_LOCAL_GENERATED_CANDIDATE_PROCESS",
        candidate_id=candidate_id,
        spec_hash="a" * 64,
        workload_ir_hash="c" * 64,
        configuration_ir_hash=configuration_hash,
        primitive_manifest_hash="d" * 64,
        generated_source_sha256="e" * 64,
        driver_sha256="f" * 64,
        compiler="c++",
        compiler_kind="gnu",
        compiler_version="test",
        compile_returncode=0,
        run_returncode=0,
        record_count=1000,
        operations=100,
        repetitions=5,
        warmup_repetitions=1,
        measurements=(
            {"name": "query_0", "operation": "point_lookup", "median_ns": 1000.0},
            {"name": "query_1", "operation": "range_scan", "median_ns": 5000.0},
            {"name": "generated_candidate", "operation": "build_end_to_end", "median_ns": 50.0},
        ),
        checksum=123,
    )


def test_weighted_query_latency_uses_mws_weights_and_route_identity() -> None:
    result = synthesize(SPEC)
    assert result.winner is not None
    measured = measured_weighted_query_latency_us(SPEC, _benchmark(result.winner.id))
    assert measured == 2.0  # 0.75 * 1 us + 0.25 * 5 us


def test_validation_point_preserves_prediction_measurement_and_config_hash() -> None:
    result = synthesize(SPEC)
    assert result.winner is not None
    benchmark = _benchmark(result.winner.id)
    point = build_candidate_validation_point(SPEC, result.winner, benchmark)
    assert point.workload_id == SPEC.name
    assert point.candidate_id == result.winner.id
    assert point.measured_weighted_query_latency_us == 2.0
    assert point.absolute_error_us == abs(result.winner.predicted_latency_us - 2.0)
    assert point.benchmark_configuration_ir_hash == "b" * 64
    assert "cross-machine" in point.as_dict()["truth_boundary"]


def test_validation_rejects_candidate_identity_mismatch() -> None:
    result = synthesize(SPEC)
    assert result.winner is not None
    try:
        build_candidate_validation_point(SPEC, result.winner, _benchmark("different"))
    except ValueError as exc:
        assert "candidate_id" in str(exc)
    else:
        raise AssertionError("candidate identity mismatch must be rejected")


def test_mutation_workloads_are_rejected_until_protocol_is_semantically_matched() -> None:
    mutation_spec = parse_workload_text(
        """
version: mws-0.1
name: mutation_validation
record_count: 100
fields:
  - name: id
    type: uint64
queries:
  - kind: point_lookup
    field: id
    weight: 0.5
  - kind: update
    weight: 0.5
""".strip()
    )
    result = synthesize(mutation_spec)
    assert result.winner is not None
    try:
        measured_weighted_query_latency_us(mutation_spec, _benchmark(result.winner.id))
    except ValueError as exc:
        assert "read-only" in str(exc)
    else:
        raise AssertionError("mutation workload must be rejected by read-only validation bridge")
