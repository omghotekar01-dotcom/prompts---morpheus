from __future__ import annotations

import pytest

from app.calibration import CALIBRATIONS
from app.catalog import PRIMITIVES
from app.cost_model import estimate_update_mix_us, estimate_update_us
from app.engine import synthesize
from app.models import (
    AccessDistribution,
    CalibrationMeasurement,
    CalibrationProfile,
    QueryDistributionSpec,
    QueryKind,
    SearchStrategy,
)
from app.parser import parse_workload_text


def _hotspot(probability: float = 0.8) -> QueryDistributionSpec:
    return QueryDistributionSpec(
        kind=AccessDistribution.HOTSPOT,
        hotspot_fraction=0.1,
        hotspot_probability=probability,
    )


def _profile(measurements: list[CalibrationMeasurement]) -> CalibrationProfile:
    return CalibrationProfile(
        id="mutation-distribution-test",
        schema_version=4,
        evidence_state="MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_DISTRIBUTION_BOUND",
        protocol="morpheus-distribution-calibration-v1",
        record_count=1000,
        operations=5000,
        seed=1337,
        machine={"cpu": "test"},
        measurements=measurements,
    )


def _spec(*mutation_blocks: str) -> str:
    blocks = "\n".join(mutation_blocks)
    return f"""
version: mws-0.1
name: mutation_distribution_test
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
queries:
  - kind: point_lookup
    field: id
    weight: 1
{blocks}
constraints:
  memory_mb: 64
  update_rate: 100
objective:
  latency: 1
  memory: 0
  update: 1
  build: 0
""".strip()


def _update_block(kind: str, *, weight: float = 1.0, probability: float = 0.8) -> str:
    return f"""  - kind: {kind}
    weight: {weight}
    distribution:
      kind: hotspot
      hotspot_fraction: 0.1
      hotspot_probability: {probability}"""


def test_update_estimate_requires_exact_operation_and_distribution() -> None:
    implementation_id = PRIMITIVES["robin_hood_hash"].implementation_id
    profile = _profile(
        [
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="insert",
                access_distribution=_hotspot(),
                ns_per_op=40.0,
                repetitions=5,
            ),
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="update",
                access_distribution=_hotspot(),
                ns_per_op=80.0,
                repetitions=5,
            ),
        ]
    )

    exact = estimate_update_us(
        "robin_hood_hash",
        profile=profile,
        record_count=1000,
        distribution=_hotspot(),
        operation=QueryKind.UPDATE,
    )
    wrong_operation = estimate_update_us(
        "robin_hood_hash",
        profile=_profile(
            [
                CalibrationMeasurement(
                    primitive="robin_hood_hash",
                    implementation_id=implementation_id,
                    operation="insert",
                    access_distribution=_hotspot(),
                    ns_per_op=40.0,
                    repetitions=5,
                )
            ]
        ),
        record_count=1000,
        distribution=_hotspot(),
        operation=QueryKind.UPDATE,
    )
    wrong_distribution = estimate_update_us(
        "robin_hood_hash",
        profile=profile,
        record_count=1000,
        distribution=_hotspot(0.9),
        operation=QueryKind.UPDATE,
    )

    assert exact.value == pytest.approx(0.08)
    assert exact.source.startswith("CALIBRATED:mutation-distribution-test")
    assert wrong_operation.source == "BOOTSTRAP_PRIOR"
    assert wrong_operation.value == pytest.approx(PRIMITIVES["robin_hood_hash"].update_latency_us)
    assert wrong_distribution.source == "BOOTSTRAP_PRIOR"


def test_mutation_mix_uses_declared_operation_weights() -> None:
    implementation_id = PRIMITIVES["robin_hood_hash"].implementation_id
    sequential = QueryDistributionSpec(kind=AccessDistribution.SEQUENTIAL)
    profile = _profile(
        [
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="insert",
                access_distribution=_hotspot(),
                ns_per_op=100.0,
                repetitions=5,
            ),
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="update",
                access_distribution=sequential,
                ns_per_op=300.0,
                repetitions=5,
            ),
        ]
    )
    spec = parse_workload_text(
        _spec(
            _update_block("insert", weight=1.0),
            """  - kind: update
    weight: 3
    distribution:
      kind: sequential""",
        )
    )

    estimate = estimate_update_mix_us(spec, "robin_hood_hash", profile=profile)
    assert estimate.value == pytest.approx(0.25)
    assert estimate.source.startswith("CALIBRATED:MUTATION_MIX:")


def test_synthesis_consumes_exact_mutation_distribution_for_physical_indexes() -> None:
    implementation_id = PRIMITIVES["robin_hood_hash"].implementation_id
    profile = _profile(
        [
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="update",
                access_distribution=_hotspot(),
                ns_per_op=40.0,
                repetitions=5,
            )
        ]
    )
    CALIBRATIONS.register(profile, persist=False)
    CALIBRATIONS.activate(profile.id, persist=False)

    exact = synthesize(
        parse_workload_text(_spec(_update_block("update"))),
        strategy=SearchStrategy.EXHAUSTIVE,
    )
    mismatched = synthesize(
        parse_workload_text(_spec(_update_block("update", probability=0.9))),
        strategy=SearchStrategy.EXHAUSTIVE,
    )

    exact_hash_candidates = [
        candidate
        for candidate in exact.candidates
        if candidate.assignments[0].primitive == "robin_hood_hash"
    ]
    mismatched_hash_candidates = [
        candidate
        for candidate in mismatched.candidates
        if candidate.assignments[0].primitive == "robin_hood_hash"
    ]
    assert exact_hash_candidates
    assert mismatched_hash_candidates
    assert all(candidate.predicted_update_us == pytest.approx(0.04) for candidate in exact_hash_candidates)
    assert all(
        candidate.predicted_update_us == pytest.approx(PRIMITIVES["robin_hood_hash"].update_latency_us)
        for candidate in mismatched_hash_candidates
    )
    assert any("CALIBRATED" in candidate.prediction_source for candidate in exact_hash_candidates)
