from __future__ import annotations

import json

from app.evidence_validation import validate_cross_artifact_links, validate_evidence_bytes


def test_structural_validator_accepts_frozen_experiment_manifest() -> None:
    payload = {
        "schema": "morpheus-experiment-manifest-v1",
        "experiments": [{"experiment_id": "mx-1"}],
    }
    result = validate_evidence_bytes("experiment_manifest", json.dumps(payload).encode())
    assert result.valid is True
    assert result.evidence_state == "EVIDENCE_STRUCTURAL_VALIDATION_PASSED"


def test_structural_validator_rejects_failed_full_verification_manifest() -> None:
    payload = {
        "schema": "morpheus-artifact-verification-v2",
        "success": False,
        "compile_gate": {},
        "behavior_gate": {},
    }
    result = validate_evidence_bytes("full_artifact_verification_manifest", json.dumps(payload).encode())
    assert result.valid is False
    assert "success=true" in result.details[0]


def test_generated_header_requires_codegen_markers() -> None:
    good = b"#pragma once\nnamespace morpheus { class GeneratedIndex {}; }\n"
    bad = b"int unrelated = 1;\n"
    assert validate_evidence_bytes("generated_header", good).valid is True
    assert validate_evidence_bytes("generated_header", bad).valid is False


def test_cross_artifact_link_detects_statistics_raw_hash_mismatch() -> None:
    errors = validate_cross_artifact_links(
        {
            "raw_measurements": {"canonical_json_sha256": "a" * 64},
            "statistical_summary": {
                "json": {"source_raw_measurements_sha256": "b" * 64},
            },
        }
    )
    assert errors and "does not match" in errors[0]
