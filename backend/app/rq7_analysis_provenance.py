from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any, Mapping

from .evidence_validation import EvidenceValidation
from .rq7_confirmatory_evidence import validate_rq7_confirmatory_analysis_payload


SOURCE_ROLE = "rq7_analysis_source"
PROVENANCE_ROLE = "rq7_analysis_provenance"
PROVENANCE_SCHEMA = "morpheus-rq7-analysis-provenance-v1"
EVIDENCE_STATE = "CONTENT_HASHED_RQ7_ANALYSIS_IMPLEMENTATION_PROVENANCE"
ANALYSIS_SOURCE_PATH = Path(__file__).with_name("rq7_confirmatory_analysis.py")

_TRUTH_BOUNDARIES = [
    "The provenance artifact binds one confirmatory-analysis JSON document to exact analysis source bytes and a recorded Python runtime identity.",
    "Source-byte identity improves reproducibility but does not prove that the Python runtime, operating system or numerical libraries are behaviorally identical on another machine.",
    "The analysis remains scoped to the measured campaign and cannot manufacture measurements or broaden the RQ7 claim boundary.",
]


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value != "0" * 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def validate_rq7_analysis_source_bytes(data: bytes) -> EvidenceValidation:
    if not data:
        return EvidenceValidation(SOURCE_ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("analysis source is empty",))
    if len(data) > 2 * 1024 * 1024:
        return EvidenceValidation(SOURCE_ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("analysis source exceeds 2 MiB",))
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return EvidenceValidation(SOURCE_ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("analysis source is not UTF-8",))
    required = (
        'SCHEMA = "morpheus-rq7-confirmatory-analysis-v1"',
        "_BOOTSTRAP_ROUNDS = 10_000",
        "_BOOTSTRAP_SEED = 7007",
        "def analyze_rq7_confirmatory(",
        "holm_bonferroni",
        "CELL_MEDIAN_WITH_MATCHED_FACTOR_BLOCKS",
    )
    missing = tuple(marker for marker in required if marker not in text)
    if missing:
        return EvidenceValidation(
            SOURCE_ROLE,
            False,
            "EVIDENCE_STRUCTURAL_VALIDATION_FAILED",
            tuple(f"analysis source missing marker: {marker}" for marker in missing),
        )
    return EvidenceValidation(
        SOURCE_ROLE,
        True,
        "EVIDENCE_STRUCTURAL_VALIDATION_PASSED",
        ("recognized frozen H7-v1 analysis source markers and deterministic bootstrap protocol",),
    )


def build_rq7_analysis_provenance(
    analysis: Mapping[str, Any],
    *,
    source_bytes: bytes | None = None,
) -> dict[str, Any]:
    validate_rq7_confirmatory_analysis_payload(analysis)
    resolved_source = ANALYSIS_SOURCE_PATH.read_bytes() if source_bytes is None else bytes(source_bytes)
    source_validation = validate_rq7_analysis_source_bytes(resolved_source)
    if not source_validation.valid:
        raise ValueError("invalid RQ7 analysis source: " + "; ".join(source_validation.details))

    runtime = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_compiler": platform.python_compiler(),
        "platform": platform.platform(),
    }
    core = {
        "schema": PROVENANCE_SCHEMA,
        "study_id": analysis["study_id"],
        "analysis_protocol_schema": analysis["schema"],
        "analysis_sha256": analysis["analysis_sha256"],
        "campaign_sha256": analysis["campaign_sha256"],
        "manifest_sha256": analysis["manifest_sha256"],
        "machine_fingerprint_sha256": analysis["machine_fingerprint_sha256"],
        "analysis_source_sha256": _sha256_bytes(resolved_source),
        "analysis_source_filename": ANALYSIS_SOURCE_PATH.name,
        "runtime": runtime,
        "evidence_state": EVIDENCE_STATE,
        "truth_boundaries": list(_TRUTH_BOUNDARIES),
    }
    return {**core, "provenance_sha256": _canonical_sha256(core)}


def validate_rq7_analysis_provenance_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("schema") != PROVENANCE_SCHEMA:
        raise ValueError("unexpected RQ7 analysis provenance schema")
    if payload.get("study_id") != "rq7-generated-migration-v1":
        raise ValueError("RQ7 analysis provenance must target rq7-generated-migration-v1")
    if payload.get("analysis_protocol_schema") != "morpheus-rq7-confirmatory-analysis-v1":
        raise ValueError("RQ7 analysis provenance has unexpected analysis protocol schema")
    for field in (
        "analysis_sha256",
        "campaign_sha256",
        "manifest_sha256",
        "machine_fingerprint_sha256",
        "analysis_source_sha256",
        "provenance_sha256",
    ):
        if not _valid_sha256(payload.get(field)):
            raise ValueError(f"RQ7 analysis provenance has invalid {field}")
    if payload.get("analysis_source_filename") != "rq7_confirmatory_analysis.py":
        raise ValueError("RQ7 analysis provenance has unexpected source filename")
    runtime = payload.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ValueError("RQ7 analysis provenance requires runtime identity")
    for field in ("python_implementation", "python_version", "python_compiler", "platform"):
        value = runtime.get(field)
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError(f"RQ7 analysis provenance runtime.{field} must be a canonical non-empty string")
    if payload.get("evidence_state") != EVIDENCE_STATE:
        raise ValueError("RQ7 analysis provenance has unexpected evidence_state")
    if payload.get("truth_boundaries") != _TRUTH_BOUNDARIES:
        raise ValueError("RQ7 analysis provenance truth boundaries are invalid")
    core = {key: value for key, value in payload.items() if key != "provenance_sha256"}
    if _canonical_sha256(core) != payload.get("provenance_sha256"):
        raise ValueError("RQ7 analysis provenance hash does not match content")


def validate_rq7_analysis_provenance_bytes(data: bytes) -> EvidenceValidation:
    try:
        payload = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return EvidenceValidation(PROVENANCE_ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("analysis provenance is not UTF-8",))
    except json.JSONDecodeError as exc:
        return EvidenceValidation(PROVENANCE_ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (f"invalid JSON: {exc.msg}",))
    if not isinstance(payload, dict):
        return EvidenceValidation(PROVENANCE_ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("top-level JSON value must be an object",))
    try:
        validate_rq7_analysis_provenance_payload(payload)
    except ValueError as exc:
        return EvidenceValidation(PROVENANCE_ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (str(exc),))
    return EvidenceValidation(
        PROVENANCE_ROLE,
        True,
        "EVIDENCE_STRUCTURAL_VALIDATION_PASSED",
        ("validated H7 analysis/source/runtime provenance identities and content hash",),
    )
