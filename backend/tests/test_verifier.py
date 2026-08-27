from __future__ import annotations

import pytest

from app.artifact_codegen import generate_verified_header
from app.engine import synthesize
from app.parser import parse_workload_text
from app.toolchain import discover_toolchain
from app.verifier import verify_generated_header_compile


SPEC = """
version: mws-0.1
name: verifier_test
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
  memory_mb: 16
""".strip()


def test_local_compile_gate_accepts_generated_cpp20_when_compiler_exists() -> None:
    if discover_toolchain() is None:
        pytest.skip("C++20 compiler unavailable")

    spec = parse_workload_text(SPEC)
    result = synthesize(spec)
    assert result.winner is not None
    artifact = generate_verified_header(spec, result.winner)
    verification = verify_generated_header_compile(artifact)

    assert verification.success, verification.stderr
    assert verification.evidence_state == "COMPILED_LOCAL_TOOLCHAIN"
    assert verification.compiler_kind in {"gnu", "msvc"}
    assert len(verification.source_sha256) == 64
    assert verification.command_policy == "FIXED_ARGUMENT_VECTOR_NO_SHELL"
    assert any("does not prove logical correctness" in item for item in verification.limitations)
