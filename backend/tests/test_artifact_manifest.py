from __future__ import annotations

from app.artifact_codegen import generate_verified_header
from app.artifact_manifest import (
    ARTIFACT_MANIFEST_VERSION,
    artifact_manifest_hash,
    build_artifact_provenance_manifest,
    canonical_artifact_manifest_json,
)
from app.engine import synthesize
from app.parser import parse_workload_text


SPEC = """
version: mws-0.1
name: artifact_manifest_demo
record_count: 5000
fields:
  - name: id
    type: uint64
    cardinality: 5000
  - name: age
    type: uint32
    cardinality: 90
queries:
  - kind: point_lookup
    field: id
    weight: 0.7
  - kind: range_scan
    field: age
    weight: 0.3
    selectivity: 0.1
constraints:
  memory_mb: 64
""".strip()


def test_artifact_manifest_binds_source_workload_configuration_and_catalog() -> None:
    spec = parse_workload_text(SPEC)
    result = synthesize(spec)
    assert result.winner is not None
    artifact = generate_verified_header(spec, result.winner, namespace_name="manifest_demo")

    first = build_artifact_provenance_manifest(spec, result.winner, artifact)
    second = build_artifact_provenance_manifest(spec, result.winner, artifact)
    assert first == second
    assert first.schema == ARTIFACT_MANIFEST_VERSION
    assert first.candidate_id == result.winner.id
    assert first.namespace_name == "manifest_demo"
    assert len(first.source_sha256) == 64
    assert len(first.workload_ir_hash) == 64
    assert len(first.configuration_ir_hash) == 64
    assert len(first.primitive_manifest_hash) == 64
    assert artifact_manifest_hash(first) == artifact_manifest_hash(second)
    assert "truth_boundary" in first.as_dict()
    assert canonical_artifact_manifest_json(first)


def test_artifact_manifest_changes_when_generated_source_changes() -> None:
    spec = parse_workload_text(SPEC)
    result = synthesize(spec)
    assert result.winner is not None
    default_artifact = generate_verified_header(spec, result.winner)
    namespaced_artifact = generate_verified_header(spec, result.winner, namespace_name="candidate_shadow")

    default_manifest = build_artifact_provenance_manifest(spec, result.winner, default_artifact)
    namespaced_manifest = build_artifact_provenance_manifest(spec, result.winner, namespaced_artifact)
    assert default_manifest.source_sha256 != namespaced_manifest.source_sha256
    assert artifact_manifest_hash(default_manifest) != artifact_manifest_hash(namespaced_manifest)
    assert default_manifest.configuration_ir_hash == namespaced_manifest.configuration_ir_hash
