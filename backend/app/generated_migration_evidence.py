from __future__ import annotations

import json
from typing import Any

from .evidence_validation import EvidenceValidation
from .generated_migration_verifier import (
    VERIFICATION_SCHEMA,
    GeneratedMigrationVerificationResult,
)


ROLE = "generated_migration_verification_manifest"
_VERIFIED_STATE = "COMPILE_AND_EXECUTION_VERIFIED_LOCAL_GENERATED_MIGRATION"


def canonical_generated_migration_manifest_bytes(
    result: GeneratedMigrationVerificationResult,
) -> bytes:
    """Serialize one verifier result as a canonical release-evidence artifact."""

    payload = result.as_dict()
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _valid_sha256(value: Any) -> bool:
    text = str(value).lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def validate_generated_migration_manifest_bytes(data: bytes) -> EvidenceValidation:
    errors: list[str] = []
    try:
        payload = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("manifest is not UTF-8",))
    except json.JSONDecodeError as exc:
        return EvidenceValidation(
            ROLE,
            False,
            "EVIDENCE_STRUCTURAL_VALIDATION_FAILED",
            (f"invalid JSON: {exc.msg}",),
        )
    if not isinstance(payload, dict):
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("top-level JSON value must be an object",))

    if payload.get("schema") != VERIFICATION_SCHEMA:
        errors.append(f"expected schema={VERIFICATION_SCHEMA!r}")
    if payload.get("success") is not True:
        errors.append("generated migration verification requires success=true")
    if payload.get("evidence_state") != _VERIFIED_STATE:
        errors.append("unexpected generated migration evidence_state")

    source_candidate = str(payload.get("source_candidate_id", "")).strip()
    target_candidate = str(payload.get("target_candidate_id", "")).strip()
    if not source_candidate or not target_candidate:
        errors.append("source_candidate_id and target_candidate_id are required")
    elif source_candidate == target_candidate:
        errors.append("source_candidate_id and target_candidate_id must be distinct")

    for field in ("source_manifest_sha256", "target_manifest_sha256", "harness_sha256"):
        if not _valid_sha256(payload.get(field)):
            errors.append(f"invalid {field}")
    if (
        _valid_sha256(payload.get("source_manifest_sha256"))
        and _valid_sha256(payload.get("target_manifest_sha256"))
        and payload.get("source_manifest_sha256") == payload.get("target_manifest_sha256")
    ):
        errors.append("source and target manifest hashes must be distinct")

    compiler = str(payload.get("compiler", "")).strip()
    compiler_kind = str(payload.get("compiler_kind", "")).strip()
    compiler_version = str(payload.get("compiler_version", "")).strip()
    if not compiler or not compiler_kind or not compiler_version:
        errors.append("compiler executable, kind and version are required")
    if payload.get("compile_returncode") != 0:
        errors.append("compile_returncode must be 0")
    if payload.get("run_returncode") != 0:
        errors.append("run_returncode must be 0")

    source_reads = payload.get("source_reads")
    target_reads = payload.get("target_reads")
    invalid_reads = payload.get("invalid_reads")
    final_generation = payload.get("final_generation")
    if not isinstance(source_reads, int) or source_reads <= 0:
        errors.append("source_reads must be a positive integer")
    if not isinstance(target_reads, int) or target_reads <= 0:
        errors.append("target_reads must be a positive integer")
    if invalid_reads != 0:
        errors.append("invalid_reads must equal 0")
    if not isinstance(final_generation, int) or final_generation < 4:
        errors.append("final_generation must be at least 4 after publish/manual rollback/health-reject rollback")

    run_stdout = str(payload.get("run_stdout", ""))
    if "MORPHEUS_GENERATED_MIGRATION_OK" not in run_stdout:
        errors.append("run_stdout lacks MORPHEUS_GENERATED_MIGRATION_OK marker")
    if "invalid_reads=0" not in run_stdout:
        errors.append("run_stdout lacks zero-invalid-reader marker")

    return EvidenceValidation(
        ROLE,
        not errors,
        "EVIDENCE_STRUCTURAL_VALIDATION_PASSED" if not errors else "EVIDENCE_STRUCTURAL_VALIDATION_FAILED",
        (
            "verified generated-migration schema, provenance hashes, local toolchain result and concurrency/rollback markers",
        )
        if not errors
        else tuple(errors),
    )
