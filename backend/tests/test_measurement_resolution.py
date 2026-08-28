from __future__ import annotations

from dataclasses import replace

from app.candidate_benchmark import CandidateBenchmarkResult
from app.configuration_ir import lower_and_hash_configuration_ir
from app.engine import synthesize
from app.measurement_resolution import resolve_ambiguous_decision
from app.models import CandidateResult, QueryKind, SearchStrategy, WorkloadSpec
from app.parser import parse_workload_text, semantic_hash
from app.primitive_manifest import primitive_manifest_hash
from app.workload_ir import lower_and_hash_workload_ir


LATENCY_ONLY_SPEC = parse_workload_text(
    """
version: mws-0.1
name: active_measurement_latency_only
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
queries:
  - kind: point_lookup
    field: id
    weight: 1.0
constraints:
  memory_mb: 64
objective:
  latency: 1.0
  memory: 0
  update: 0
  build: 0
""".strip()
)

MULTI_OBJECTIVE_SPEC = parse_workload_text(
    """
version: mws-0.1
name: active_measurement_multi_objective
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
queries:
  - kind: point_lookup
    field: id
    weight: 1.0
constraints:
  memory_mb: 64
objective:
  latency: 1.0
  memory: 0.25
  update: 0
  build: 0
""".strip()
)


def _query_distributions(spec: WorkloadSpec) -> tuple[dict[str, object], ...]:
    mutations = {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}
    return tuple(
        {
            "query_index": index,
            **query.distribution.model_dump(mode="json", exclude_none=True),
        }
        for index, query in enumerate(spec.queries)
        if query.kind not in mutations
    )


def _successful_benchmark(
    spec: WorkloadSpec,
    candidate: CandidateResult,
    *,
    median_ns: float,
) -> CandidateBenchmarkResult:
    measurements = tuple(
        {
            "name": f"query_{index}",
            "operation": query.kind.value,
            "median_ns": median_ns,
            "mean_ns": median_ns,
            "stdev_ns": 0.0,
            "min_ns": median_ns,
            "max_ns": median_ns,
            "samples_ns": [median_ns],
        }
        for index, query in enumerate(spec.queries)
    )
    _workload_ir, workload_ir_hash = lower_and_hash_workload_ir(spec)
    _configuration_ir, configuration_ir_hash = lower_and_hash_configuration_ir(spec, candidate)
    return CandidateBenchmarkResult(
        success=True,
        evidence_state="MEASURED_LOCAL_GENERATED_CANDIDATE_PROCESS",
        candidate_id=candidate.id,
        spec_hash=semantic_hash(spec),
        workload_ir_hash=workload_ir_hash,
        configuration_ir_hash=configuration_ir_hash,
        primitive_manifest_hash=primitive_manifest_hash(),
        generated_source_sha256="5" * 64,
        driver_sha256="6" * 64,
        compiler="fake-cxx",
        compiler_kind="gnu",
        compiler_version="test",
        compile_returncode=0,
        run_returncode=0,
        record_count=spec.record_count,
        operations=100,
        repetitions=1,
        warmup_repetitions=0,
        measurements=measurements,
        checksum=1,
        query_distributions=_query_distributions(spec),
    )


def _failing_benchmark(spec: WorkloadSpec, candidate: CandidateResult) -> CandidateBenchmarkResult:
    _workload_ir, workload_ir_hash = lower_and_hash_workload_ir(spec)
    _configuration_ir, configuration_ir_hash = lower_and_hash_configuration_ir(spec, candidate)
    return CandidateBenchmarkResult(
        success=False,
        evidence_state="CANDIDATE_BENCHMARK_COMPILE_FAILED",
        candidate_id=candidate.id,
        spec_hash=semantic_hash(spec),
        workload_ir_hash=workload_ir_hash,
        configuration_ir_hash=configuration_ir_hash,
        primitive_manifest_hash=primitive_manifest_hash(),
        generated_source_sha256="5" * 64,
        driver_sha256="6" * 64,
        compiler="fake-cxx",
        compiler_kind="gnu",
        compiler_version="test",
        compile_returncode=1,
        run_returncode=None,
        record_count=spec.record_count,
        operations=100,
        repetitions=1,
        warmup_repetitions=0,
        measurements=(),
        checksum=None,
        query_distributions=_query_distributions(spec),
        compile_stderr="synthetic test failure",
    )


def test_ambiguous_latency_only_finalists_can_be_resolved_by_same_scale_measurement() -> None:
    result = synthesize(LATENCY_ONLY_SPEC, strategy=SearchStrategy.EXHAUSTIVE)
    assert result.winner is not None
    calls: list[tuple[str, int]] = []

    def fake_runner(spec: WorkloadSpec, candidate: CandidateResult, **kwargs) -> CandidateBenchmarkResult:
        calls.append((candidate.id, int(kwargs["record_count"])))
        median_ns = 2000.0 if candidate.id == result.winner.id else 500.0 + 100.0 * len(calls)
        return _successful_benchmark(spec, candidate, median_ns=median_ns)

    report = resolve_ambiguous_decision(
        LATENCY_ONLY_SPEC,
        result,
        interval_scale=10.0,
        max_candidates_to_measure=3,
        operations=100,
        repetitions=1,
        warmup=0,
        benchmark_runner=fake_runner,
    )

    assert report.confidence_assessment.action == "BENCHMARK_MORE"
    assert len(calls) >= 2
    assert all(record_count == LATENCY_ONLY_SPEC.record_count for _, record_count in calls)
    assert report.empirical_selection_allowed
    assert report.action == "EMPIRICAL_FINALIST_SWITCH"
    assert report.resolved_winner_id is not None
    assert report.resolved_winner_id != result.winner.id
    assert report.evidence_state == "LOCAL_SAME_SCALE_DISTRIBUTION_BOUND_GENERATED_CANDIDATE_FINALIST_DECISION"


def test_multi_objective_measurements_never_silently_replace_unmeasured_objective_terms() -> None:
    result = synthesize(MULTI_OBJECTIVE_SPEC, strategy=SearchStrategy.EXHAUSTIVE)
    assert result.winner is not None

    def fake_runner(spec: WorkloadSpec, candidate: CandidateResult, **kwargs) -> CandidateBenchmarkResult:
        median_ns = 100.0 if candidate.id != result.winner.id else 5000.0
        return _successful_benchmark(spec, candidate, median_ns=median_ns)

    report = resolve_ambiguous_decision(
        MULTI_OBJECTIVE_SPEC,
        result,
        interval_scale=10.0,
        max_candidates_to_measure=3,
        operations=100,
        repetitions=1,
        warmup=0,
        benchmark_runner=fake_runner,
    )

    assert report.confidence_assessment.action == "BENCHMARK_MORE"
    assert report.measured_candidates
    assert not report.empirical_selection_allowed
    assert report.action == "MEASUREMENTS_COLLECTED_REVIEW_REQUIRED"
    assert report.resolved_winner_id == result.winner.id
    assert "non-latency objective components" in report.empirical_selection_reason


def test_incomplete_active_measurement_fails_closed_to_modeled_winner() -> None:
    result = synthesize(LATENCY_ONLY_SPEC, strategy=SearchStrategy.EXHAUSTIVE)
    assert result.winner is not None
    call_count = 0

    def fake_runner(spec: WorkloadSpec, candidate: CandidateResult, **kwargs) -> CandidateBenchmarkResult:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _successful_benchmark(spec, candidate, median_ns=2000.0)
        return _failing_benchmark(spec, candidate)

    report = resolve_ambiguous_decision(
        LATENCY_ONLY_SPEC,
        result,
        interval_scale=10.0,
        max_candidates_to_measure=2,
        operations=100,
        repetitions=1,
        warmup=0,
        benchmark_runner=fake_runner,
    )

    assert report.action == "ACTIVE_MEASUREMENT_INCOMPLETE_KEEP_MODELED_WINNER"
    assert report.resolved_winner_id == result.winner.id
    assert any(not item.benchmark_success for item in report.measured_candidates)


def test_tampered_measurement_provenance_fails_closed_to_modeled_winner() -> None:
    result = synthesize(LATENCY_ONLY_SPEC, strategy=SearchStrategy.EXHAUSTIVE)
    assert result.winner is not None

    def fake_runner(spec: WorkloadSpec, candidate: CandidateResult, **kwargs) -> CandidateBenchmarkResult:
        benchmark = _successful_benchmark(spec, candidate, median_ns=100.0)
        return replace(benchmark, workload_ir_hash="0" * 64)

    report = resolve_ambiguous_decision(
        LATENCY_ONLY_SPEC,
        result,
        interval_scale=10.0,
        max_candidates_to_measure=2,
        operations=100,
        repetitions=1,
        warmup=0,
        benchmark_runner=fake_runner,
    )

    assert report.action == "ACTIVE_MEASUREMENT_INCOMPLETE_KEEP_MODELED_WINNER"
    assert report.resolved_winner_id == result.winner.id
    assert report.measured_candidates
    assert all(item.benchmark_evidence_state == "MEASUREMENT_PROVENANCE_REJECTED" for item in report.measured_candidates)
    assert all(not item.benchmark_success for item in report.measured_candidates)


def test_non_ambiguous_decision_does_not_invoke_benchmark_runner() -> None:
    result = synthesize(LATENCY_ONLY_SPEC, strategy=SearchStrategy.EXHAUSTIVE)
    assert result.winner is not None

    def should_not_run(*args, **kwargs):
        raise AssertionError("benchmark runner must not execute for a non-ambiguous modeled decision")

    report = resolve_ambiguous_decision(
        LATENCY_ONLY_SPEC,
        result,
        interval_scale=0.0,
        benchmark_runner=should_not_run,
    )

    assert report.confidence_assessment.action == "ACCEPT_MODELED_WINNER"
    assert report.action == "ACCEPT_MODELED_WINNER_WITHOUT_ACTIVE_MEASUREMENT"
    assert report.measured_candidates == ()
    assert report.resolved_winner_id == result.winner.id
