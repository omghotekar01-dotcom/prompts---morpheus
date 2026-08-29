from __future__ import annotations

from app.artifact_codegen import generate_verified_header
from app.candidate_benchmark import benchmark_generated_candidate, generate_candidate_benchmark_driver
from app.engine import synthesize
from app.parser import parse_workload_text
from app.toolchain import discover_toolchain


SPEC = parse_workload_text(
    """
version: mws-0.1
name: candidate_benchmark_smoke
record_count: 500
fields:
  - name: id
    type: uint64
    cardinality: 500
  - name: age
    type: uint32
    cardinality: 80
  - name: city
    type: string
    cardinality: 16
queries:
  - kind: point_lookup
    field: id
    weight: 0.5
  - kind: range_scan
    field: age
    weight: 0.25
    selectivity: 0.1
  - kind: filter
    field: city
    weight: 0.25
constraints:
  memory_mb: 64
""".strip()
)

DISTRIBUTION_SPEC = parse_workload_text(
    """
version: mws-0.1
name: candidate_distribution_driver
record_count: 500
fields:
  - name: id
    type: uint64
    cardinality: 500
queries:
  - kind: point_lookup
    field: id
    weight: 0.34
    distribution:
      kind: hotspot
      hotspot_fraction: 0.1
      hotspot_probability: 0.8
  - kind: point_lookup
    field: id
    weight: 0.33
    distribution:
      kind: sequential
  - kind: point_lookup
    field: id
    weight: 0.33
    distribution:
      kind: zipf
      zipf_theta: 1.15
constraints:
  memory_mb: 64
objective:
  latency: 1.0
  memory: 0
  update: 0
  build: 0
""".strip()
)


def test_candidate_benchmark_driver_is_bound_to_winner_routes() -> None:
    result = synthesize(SPEC)
    assert result.winner is not None
    artifact = generate_verified_header(SPEC, result.winner)
    driver = generate_candidate_benchmark_driver(SPEC, result.winner, artifact)
    assert artifact.header_name in driver
    assert result.winner.id in driver
    assert '"build_end_to_end"' in driver
    assert '"point_lookup"' in driver
    assert '"range_scan"' in driver
    assert '"filter"' in driver
    assert '"update_record"' in driver


def test_candidate_driver_precomputes_each_declared_access_distribution() -> None:
    result = synthesize(DISTRIBUTION_SPEC)
    assert result.winner is not None
    artifact = generate_verified_header(DISTRIBUTION_SPEC, result.winner)
    driver = generate_candidate_benchmark_driver(DISTRIBUTION_SPEC, result.winner, artifact)

    assert "const auto q0_rows = make_hotspot_rows" in driver
    assert "const auto q1_rows = make_sequential_rows" in driver
    assert "const auto q2_rows = make_zipf_rows" in driver
    assert "for (std::size_t i = 0; i < operations; ++i)" in driver
    # Query loops consume precomputed qN_rows. Distribution generation must not be inside the timed callback.
    assert "make_hotspot_rows(n, operations" in driver
    assert "make_zipf_rows(n, operations" in driver


def test_generated_candidate_benchmark_compiles_runs_and_preserves_provenance() -> None:
    if discover_toolchain() is None:
        return
    synthesis = synthesize(SPEC)
    assert synthesis.winner is not None
    measured = benchmark_generated_candidate(
        SPEC,
        synthesis.winner,
        record_count=128,
        operations=64,
        repetitions=2,
        warmup=0,
        compile_timeout_seconds=90,
        run_timeout_seconds=60,
    )
    assert measured.success, measured.as_dict()
    assert measured.evidence_state == "MEASURED_LOCAL_GENERATED_CANDIDATE_PROCESS"
    assert measured.candidate_id == synthesis.winner.id
    assert len(measured.workload_ir_hash) == 64
    assert len(measured.configuration_ir_hash) == 64
    assert len(measured.primitive_manifest_hash) == 64
    assert len(measured.generated_source_sha256) == 64
    assert len(measured.driver_sha256) == 64
    assert measured.record_count == 128
    assert measured.distribution_protocol == "morpheus-access-distribution-v1"
    assert len(measured.query_distributions) == len(SPEC.queries)
    assert all(item["kind"] == "uniform" for item in measured.query_distributions)
    operations = {item["operation"] for item in measured.measurements}
    assert {"build_end_to_end", "point_lookup", "range_scan", "filter", "update_record"} <= operations
    assert all(float(item["median_ns"]) >= 0 for item in measured.measurements)
    assert measured.checksum is not None and measured.checksum > 0
    assert "not publication-grade" in measured.as_dict()["truth_boundary"]
