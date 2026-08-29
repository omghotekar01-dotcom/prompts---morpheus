from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.engine import synthesize
from app.generated_migration_bundle import (
    GENERATED_MIGRATION_BUNDLE_SCHEMA,
    build_generated_migration_bundle,
    select_distinct_migration_pair,
)
from app.parser import parse_workload_text


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"
CORE_INCLUDE = REPO_ROOT / "core" / "include"


def _migration_pair():
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    source, target = select_distinct_migration_pair(synthesis)
    return spec, source, target


def _native_compiler() -> tuple[str, str] | None:
    configured = os.environ.get("MORPHEUS_CXX")
    if configured:
        resolved = shutil.which(configured)
        if resolved:
            name = Path(resolved).name.lower()
            return resolved, "msvc" if name in {"cl", "cl.exe"} else "unix"
    for candidate in ("g++", "clang++"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved, "unix"
    return None


def test_generated_migration_bundle_is_deterministic_and_provenance_bound() -> None:
    spec, source, target = _migration_pair()
    assert source.id != target.id
    assert source.assignments != target.assignments

    first = build_generated_migration_bundle(spec, source, target, record_count=64)
    second = build_generated_migration_bundle(spec, source, target, record_count=64)

    assert first.schema == GENERATED_MIGRATION_BUNDLE_SCHEMA
    assert first.source_candidate_id == source.id
    assert first.target_candidate_id == target.id
    assert first.source_manifest.workload_ir_hash == first.target_manifest.workload_ir_hash
    assert first.source_manifest.configuration_ir_hash != first.target_manifest.configuration_ir_hash
    assert first.source_artifact.namespace_name.startswith("morpheus_source_")
    assert first.target_artifact.namespace_name.startswith("morpheus_target_")
    assert first.source_artifact.namespace_name != first.target_artifact.namespace_name
    assert first.harness_sha256 == hashlib.sha256(first.harness_source.encode("utf-8")).hexdigest()
    assert first.harness_sha256 == second.harness_sha256
    assert first.source_artifact.header_source == second.source_artifact.header_source
    assert first.target_artifact.header_source == second.target_artifact.header_source
    assert '#include "morpheus/migration_publish.hpp"' in first.harness_source
    assert "migrate_publish_with_health_gate<Source, Target>" in first.harness_source
    assert "MORPHEUS_GENERATED_MIGRATION_OK" in first.harness_source
    assert "invalid_reads" in first.harness_source

    compact = first.as_dict(include_sources=False)
    assert compact["evidence_state"] == "GENERATED_MIGRATION_BUNDLE_NOT_COMPILE_VERIFIED"
    assert "harness_source" not in compact
    assert compact["source_manifest"]["candidate_id"] == source.id
    assert compact["target_manifest"]["candidate_id"] == target.id
    assert "not runtime or performance evidence" in compact["truth_boundary"]


def test_generated_migration_bundle_rejects_invalid_pair_or_size() -> None:
    spec, source, target = _migration_pair()
    with pytest.raises(ValueError, match="distinct"):
        build_generated_migration_bundle(spec, source, source)
    with pytest.raises(ValueError, match="between 1 and 4096"):
        build_generated_migration_bundle(spec, source, target, record_count=0)


def test_generated_distinct_candidates_compile_migrate_publish_and_rollback(tmp_path: Path) -> None:
    native = _native_compiler()
    if native is None:
        pytest.skip("C++20 compiler is unavailable in this environment")
    compiler, family = native

    spec, source, target = _migration_pair()
    bundle = build_generated_migration_bundle(spec, source, target, record_count=128)

    source_header = tmp_path / bundle.source_artifact.header_name
    target_header = tmp_path / bundle.target_artifact.header_name
    harness = tmp_path / "generated_migration_harness.cpp"
    source_header.write_text(bundle.source_artifact.header_source, encoding="utf-8")
    target_header.write_text(bundle.target_artifact.header_source, encoding="utf-8")
    harness.write_text(bundle.harness_source, encoding="utf-8")

    if family == "msvc":
        binary = tmp_path / "generated_migration_harness.exe"
        command = [
            compiler,
            "/nologo",
            "/std:c++20",
            "/EHsc",
            "/W4",
            "/permissive-",
            f"/I{CORE_INCLUDE}",
            f"/I{tmp_path}",
            str(harness),
            f"/Fe{binary}",
        ]
    else:
        binary = tmp_path / "generated_migration_harness"
        command = [
            compiler,
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-pthread",
            "-I",
            str(CORE_INCLUDE),
            "-I",
            str(tmp_path),
            str(harness),
            "-o",
            str(binary),
        ]

    compiled = subprocess.run(
        command,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert compiled.returncode == 0, compiled.stdout + "\n" + compiled.stderr
    assert binary.exists()

    executed = subprocess.run(
        [str(binary)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert executed.returncode == 0, executed.stdout + "\n" + executed.stderr
    assert "MORPHEUS_GENERATED_MIGRATION_OK" in executed.stdout
    assert "invalid_reads=0" in executed.stdout
