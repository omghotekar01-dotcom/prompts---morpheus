from __future__ import annotations

import pytest

from app.artifact_codegen import generate_verified_header
from app.behavior_verifier import generate_stateful_driver, verify_generated_artifact_behavior
from app.engine import synthesize
from app.parser import parse_workload_text
from app.toolchain import discover_toolchain


SPEC = """
version: mws-0.1
name: generic_behavior_gate
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
  - name: age
    type: uint32
    cardinality: 100
  - name: name
    type: string
    cardinality: 1000
  - name: team
    type: string
    cardinality: 12
queries:
  - kind: point_lookup
    field: id
    weight: 0.25
  - kind: range_scan
    field: age
    weight: 0.25
    selectivity: 0.20
  - kind: prefix_search
    field: name
    weight: 0.25
  - kind: filter
    field: team
    weight: 0.25
constraints:
  memory_mb: 64
""".strip()


def test_schema_derived_driver_contains_independent_reference_checks() -> None:
    spec = parse_workload_text(SPEC)
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    artifact = generate_verified_header(spec, synthesis.winner)
    source, checks = generate_stateful_driver(spec, synthesis.winner, artifact)
    assert "assert_same_multiset" in source
    assert "index.records() == reference" in source
    assert "query_0" in source
    assert "query_1" in source
    assert "query_2" in source
    assert "query_3" in source
    assert checks >= 20


def test_schema_derived_behavior_gate_executes_when_compiler_exists() -> None:
    if discover_toolchain() is None:
        pytest.skip("C++20 compiler unavailable")
    spec = parse_workload_text(SPEC)
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    artifact = generate_verified_header(spec, synthesis.winner)
    verification = verify_generated_artifact_behavior(spec, synthesis.winner, artifact)
    assert verification.success, verification.compile_stderr + verification.run_stderr
    assert verification.evidence_state == "STATEFUL_DIFFERENTIAL_VERIFIED_LOCAL_TOOLCHAIN"
    assert verification.driver_sha256 is not None and len(verification.driver_sha256) == 64
    assert verification.checks >= 20
