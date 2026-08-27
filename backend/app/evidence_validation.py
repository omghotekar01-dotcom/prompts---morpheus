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
    "external_baseline_manifest": ("schema", "morpheus-external-baseline-manifest-v1"),
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


def _valid_sha256(value: Any) -> bool:
    text = str(value).lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


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
            "morpheus-external-baseline-measurements-v1",
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
        if not _valid_sha256(source_hash):
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

    if role == "external_baseline_manifest":
        required_text = ("baseline_id", "project_name", "source_url", "source_revision", "license", "evidence_state")
        missing_text = [field for field in required_text if not str(payload.get(field, "")).strip()]
        if missing_text:
            return EvidenceValidation(
                role,
                False,
                "EVIDENCE_STRUCTURAL_VALIDATION_FAILED",
                tuple(f"missing required external-baseline field: {field}" for field in missing_text),
            )
        if payload.get("baseline_tier") not in {
            "B_SPECIALIST_CONTAINER",
            "C_SPECIALIST_ORDERED_INDEX",
            "D_SYSTEM_LEVEL",
        }:
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("invalid external baseline tier",))
        if not str(payload.get("source_url", "")).startswith("https://"):
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("external baseline source_url must use https://",))
        for field in ("adapter_sha256", "workload_manifest_sha256", "machine_profile_sha256"):
            if not _valid_sha256(payload.get(field)):
                return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (f"invalid {field}",))
        compiler = payload.get("compiler")
        if not isinstance(compiler, dict) or not str(compiler.get("id", "")).strip() or not str(compiler.get("version", "")).strip():
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("external baseline compiler identity/version required",))
        if not isinstance(payload.get("supported_operations"), list) or not payload["supported_operations"]:
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("external baseline supported_operations cannot be empty",))
        if not isinstance(payload.get("fairness_notes"), list) or not payload["fairness_notes"]:
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("external baseline fairness_notes cannot be empty",))
        if payload.get("evidence_state") != "EXTERNAL_BASELINE_IDENTITY_FROZEN_NOT_PERFORMANCE_ATTESTATION":
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("unexpected external baseline evidence_state",))

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

    external = artifacts.get("external_baseline_manifest")
    machine = artifacts.get("machine_profile")
    if external is not None and machine is not None:
        payload = external.get("json")
        if isinstance(payload, dict):
            expected = str(payload.get("machine_profile_sha256", "")).lower()
            actual = str(machine.get("canonical_json_sha256", "")).lower()
            if expected and actual and expected != actual:
                errors.append(
                    f"external_baseline_manifest machine_profile_sha256={expected} does not match packaged machine_profile canonical JSON hash={actual}"
                )
    return errors
