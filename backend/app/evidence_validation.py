from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceValidation:
    role: str
    valid: bool
    evidence_state: str
    details: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "valid": self.valid,
            "evidence_state": self.evidence_state,
            "details": list(self.details),
            "truth_note": (
                "Structural validation checks declared schema/protocol and cross-field invariants only; it does not independently attest measurement methodology or scientific validity."
            ),
        }


_JSON_CONTRACTS: dict[str, tuple[str, str]] = {
    "experiment_manifest": ("schema", "morpheus-experiment-manifest-v1"),
    "machine_profile": ("protocol", "morpheus-machine-profile-v1"),
    "baseline_manifest": ("schema", "morpheus-baseline-manifest-v1"),
    "statistical_summary": ("schema", "morpheus-standard-baseline-statistics-v1"),
    "full_artifact_verification_manifest": ("schema", "morpheus-artifact-verification-v2"),
    "release_manifest": ("schema", "morpheus-release-manifest-v2"),
}


def _json_object(data: bytes) -> tuple[dict[str, Any] | None, str | None]:
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "not UTF-8"
    try:
        value = json.loads(decoded)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc.msg}"
    if not isinstance(value, dict):
        return None, "top-level JSON value must be an object"
    return value, None


def validate_evidence_bytes(role: str, data: bytes) -> EvidenceValidation:
    role = role.strip()
    if not role:
        raise ValueError("evidence role cannot be empty")
    if not data:
        return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("artifact is empty",))

    if role == "generated_header":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("generated header is not UTF-8",))
        required = ("#pragma once", "class GeneratedIndex", "namespace morpheus")
        missing = tuple(token for token in required if token not in text)
        return EvidenceValidation(
            role,
            not missing,
            "EVIDENCE_STRUCTURAL_VALIDATION_PASSED" if not missing else "EVIDENCE_STRUCTURAL_VALIDATION_FAILED",
            ("recognized generated C++20 header markers",) if not missing else tuple(f"missing marker: {token}" for token in missing),
        )

    payload, error = _json_object(data)
    if error is not None:
        return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (error,))
    assert payload is not None

    if role in _JSON_CONTRACTS:
        field, expected = _JSON_CONTRACTS[role]
        actual = payload.get(field)
        if actual != expected:
            return EvidenceValidation(
                role,
                False,
                "EVIDENCE_STRUCTURAL_VALIDATION_FAILED",
                (f"expected {field}={expected!r}; got {actual!r}",),
            )

    if role == "raw_measurements":
        protocol = payload.get("protocol")
        if protocol not in {
            "morpheus-standard-baseline-matrix-v1",
            "morpheus-calibration-v2",
            "morpheus-runtime-adaptation-experiment-v1",
        }:
            return EvidenceValidation(
                role,
                False,
                "EVIDENCE_STRUCTURAL_VALIDATION_FAILED",
                (f"unrecognized raw measurement protocol: {protocol!r}",),
            )
        if protocol == "morpheus-standard-baseline-matrix-v1" and not isinstance(payload.get("runs"), list):
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("baseline matrix runs must be an array",))

    if role == "statistical_summary":
        source_hash = str(payload.get("source_raw_measurements_sha256", ""))
        if len(source_hash) != 64 or any(ch not in "0123456789abcdef" for ch in source_hash.lower()):
            return EvidenceValidation(
                role,
                False,
                "EVIDENCE_STRUCTURAL_VALIDATION_FAILED",
                ("statistical summary lacks a valid source raw-measurements SHA-256",),
            )
        if not isinstance(payload.get("comparisons"), dict):
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("comparisons must be an object",))

    if role == "machine_profile" and not isinstance(payload.get("platform"), dict):
        return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("machine profile lacks platform object",))

    if role == "experiment_manifest":
        experiments = payload.get("experiments")
        if not isinstance(experiments, list) or not experiments:
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("experiment manifest has no frozen experiments",))

    if role == "full_artifact_verification_manifest":
        if payload.get("success") is not True:
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("full verification manifest does not record success=true",))
        if not isinstance(payload.get("compile_gate"), dict) or not isinstance(payload.get("behavior_gate"), dict):
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("full verification manifest lacks compile/behavior gates",))

    if role == "release_manifest":
        if payload.get("release_state") not in {"CLAIMS_EVIDENCE_COMPLETE", "BLOCKED_BY_CLAIM_EVIDENCE"}:
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("release manifest has invalid release_state",))
        if not isinstance(payload.get("available_evidence_roles"), list):
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("release manifest lacks available_evidence_roles array",))

    # Roles with no strict in-repo schema are still required to be well-formed
    # JSON at package time. The package reports that limited validation level.
    detail = (
        f"validated contract {_JSON_CONTRACTS[role][0]}={_JSON_CONTRACTS[role][1]}"
        if role in _JSON_CONTRACTS
        else "validated as a non-empty JSON object; no stronger in-repo schema is registered for this role"
    )
    return EvidenceValidation(role, True, "EVIDENCE_STRUCTURAL_VALIDATION_PASSED", (detail,))


def validate_cross_artifact_links(artifacts: dict[str, dict[str, Any]]) -> list[str]:
    """Validate hash links that can be checked without interpreting scientific truth."""

    errors: list[str] = []
    raw = artifacts.get("raw_measurements")
    stats = artifacts.get("statistical_summary")
    if raw is not None and stats is not None:
        stats_payload = stats.get("json")
        if isinstance(stats_payload, dict):
            expected = str(stats_payload.get("source_raw_measurements_sha256", "")).lower()
            actual = str(raw.get("canonical_json_sha256", "")).lower()
            if expected and actual and expected != actual:
                errors.append(
                    f"statistical_summary source_raw_measurements_sha256={expected} does not match packaged raw_measurements canonical JSON hash={actual}"
                )
    return errors
