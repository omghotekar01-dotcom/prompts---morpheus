from __future__ import annotations

import pytest

from app.candidate_benchmark import CandidateBenchmarkResult
from app.catalog import PRIMITIVES
from app.cost_model import estimate_query_latency_us
from app.engine import synthesize
from app.measurement_resolution import resolve_ambiguous_decision
from app.models import AccessDistribution, CalibrationMeasurement, CalibrationProfile, SearchStrategy
from app.parser import SpecParseError, parse_workload_document, parse_workload_text, semantic_hash
from app.workload_ir import WORKLOAD_IR_VERSION, lower_and_hash_workload_ir


BASE = """
version: mws-0.1
name: distribution_test
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

HOTSPOT = BASE.replace(
    "    weight: 1.0",
    """    weight: 1.0
    distribution:
      kind: hotspot""",
)

ZIPF = BASE.replace(
    "    weight: 1.0",
    """    weight: 1.0
    distribution:
      kind: zipf
      zipf_theta: 1.15""",
)


def test_distribution_defaults_are_explicit_and_provenance_is_preserved() -> None:
    uniform_document = parse_workload_document(BASE)
    uniform = uniform_document.resolved_spec.queries[0].distribution
    assert uniform.kind == AccessDistribution.UNIFORM
    assert any("distribution defaulted to uniform" in item for item in uniform_document.assumptions)

    hotspot_document = parse_workload_document(HOTSPOT)
    hotspot = hotspot_document.resolved_spec.queries[0].distribution
    assert hotspot.kind == AccessDistribution.HOTSPOT
    assert hotspot.hotspot_fraction == pytest.approx(0.10)
    assert hotspot.hotspot_probability == pytest.approx(0.80)
    assert hotspot.parameters_defaulted
    assert any("hotspot parameters resolved" in item for item in hotspot_document.assumptions)


def test_distribution_changes_semantic_and_workload_ir_identity() -> None:
    uniform = parse_workload_text(BASE)
    hotspot = parse_workload_text(HOTSPOT)
    zipf = parse_workload_text(ZIPF)

    assert semantic_hash(uniform) != semantic_hash(hotspot)
    assert semantic_hash(hotspot) != semantic_hash(zipf)

    uniform_ir, uniform_hash = lower_and_hash_workload_ir(uniform)
    hotspot_ir, hotspot_hash = lower_and_hash_workload_ir(hotspot)
    assert uniform_ir.ir_version == WORKLOAD_IR_VERSION == "morpheus-workload-ir-v2"
    assert uniform_ir.operations[0].distribution.kind == AccessDistribution.UNIFORM
    assert hotspot_ir.operations[0].distribution.kind == AccessDistribution.HOTSPOT
    assert hotspot_ir.operations[0].distribution.hotspot_fraction == pytest.approx(0.10)
    assert uniform_hash != hotspot_hash


def test_irrelevant_distribution_parameters_are_rejected() -> None:
    invalid = BASE.replace(
        "    weight: 1.0",
        """    weight: 1.0
    distribution:
      kind: sequential
      zipf_theta: 1.2""",
    )
    with pytest.raises(SpecParseError, match="does not accept skew parameters"):
        parse_workload_text(invalid)


def test_uniform_calibration_is_not_mislabeled_as_nonuniform_evidence() -> None:
    uniform = parse_workload_text(BASE)
    hotspot = parse_workload_text(HOTSPOT)
    implementation_id = PRIMITIVES["robin_hood_hash"].implementation_id
    profile = CalibrationProfile(
        id="distribution-calibration",
        schema_version=3,
        evidence_state="MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_BOUND",
        protocol="morpheus-calibration-v3",
        record_count=1000,
        operations=5000,
        measurements=[
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="point_lookup",
                ns_per_op=10.0,
                repetitions=3,
            )
        ],
    )

    uniform_estimate = estimate_query_latency_us(
        uniform,
        uniform.queries[0],
        "robin_hood_hash",
        profile=profile,
    )
    hotspot_estimate = estimate_query_latency_us(
        hotspot,
        hotspot.queries[0],
        "robin_hood_hash",
        profile=profile,
    )

    assert uniform_estimate.source.startswith("CALIBRATED:distribution-calibration")
    assert hotspot_estimate.source == "BOOTSTRAP_PRIOR_DISTRIBUTION_UNMODELED:hotspot"
    assert hotspot_estimate.uncertainty_ratio == pytest.approx(0.80)


def test_active_measurement_runs_distribution_aware_harness_for_nonuniform_mws() -> None:
    spec = parse_workload_text(HOTSPOT)
    result = synthesize(spec, strategy=SearchStrategy.EXHAUSTIVE)
    assert result.winner is not None
    calls: list[str] = []

    def failing_distribution_runner(spec_arg, candidate, **kwargs):
        calls.append(candidate.id)
        return CandidateBenchmarkResult(
            success=False,
            evidence_state="SYNTHETIC_DISTRIBUTION_AWARE_FAILURE",
            candidate_id=candidate.id,
            spec_hash=semantic_hash(spec_arg),
            workload_ir_hash=lower_and_hash_workload_ir(spec_arg)[1],
            configuration_ir_hash="0" * 64,
            primitive_manifest_hash="0" * 64,
            generated_source_sha256="0" * 64,
            driver_sha256="0" * 64,
            compiler=None,
            compiler_kind=None,
            compiler_version=None,
            compile_returncode=1,
            run_returncode=None,
            record_count=int(kwargs["record_count"]),
            operations=int(kwargs["operations"]),
            repetitions=int(kwargs["repetitions"]),
            warmup_repetitions=int(kwargs["warmup"]),
            measurements=(),
            checksum=None,
            query_distributions=tuple(
                {
                    "query_index": index,
                    **query.distribution.model_dump(mode="json", exclude_none=True),
                }
                for index, query in enumerate(spec_arg.queries)
            ),
        )

    report = resolve_ambiguous_decision(
        spec,
        result,
        interval_scale=10.0,
        benchmark_runner=failing_distribution_runner,
    )
    assert report.confidence_assessment.action == "BENCHMARK_MORE"
    assert len(calls) >= 2
    assert report.action == "ACTIVE_MEASUREMENT_INCOMPLETE_KEEP_MODELED_WINNER"
    assert report.measured_candidates
    assert report.resolved_winner_id == result.winner.id
    assert report.evidence_state == "PARTIAL_OR_REJECTED_LOCAL_GENERATED_CANDIDATE_MEASUREMENT"
