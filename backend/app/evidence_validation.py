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
    "distribution_calibration_manifest": ("protocol", "morpheus-distribution-calibration-matrix-v1"),
    "full_artifact_verification_manifest": ("schema", "morpheus-artifact-verification-v2"),
    "release_manifest": ("schema", "morpheus-release-manifest-v2"),
}

_DISTRIBUTION_KINDS = {"uniform", "sequential", "hotspot", "zipf"}


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


def _valid_git_sha(value: Any) -> bool:
    text = str(value).lower()
    return len(text) == 40 and all(ch in "0123456789abcdef" for ch in text)


def _validate_distribution_identity(distribution: Any, *, prefix: str) -> tuple[str, ...]:
    if not isinstance(distribution, dict):
        return (f"{prefix} access_distribution must be an object",)
    kind = distribution.get("kind")
    if kind not in _DISTRIBUTION_KINDS:
        return (f"{prefix} has unsupported access distribution {kind!r}",)
    if kind == "zipf":
        theta = distribution.get("zipf_theta")
        if not isinstance(theta, (int, float)) or theta <= 0:
            return (f"{prefix} zipf distribution requires positive zipf_theta",)
    if kind == "hotspot":
        fraction = distribution.get("hotspot_fraction")
        probability = distribution.get("hotspot_probability")
        if not isinstance(fraction, (int, float)) or not 0 < fraction <= 1:
            return (f"{prefix} hotspot distribution requires 0 < hotspot_fraction <= 1",)
        if not isinstance(probability, (int, float)) or not 0 < probability <= 1:
            return (f"{prefix} hotspot distribution requires 0 < hotspot_probability <= 1",)
    return ()


def _validate_distribution_raw_measurements(payload: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if payload.get("schema_version") != 4:
        errors.append("distribution calibration raw measurements require schema_version=4")
    if payload.get("distribution_protocol") != "morpheus-access-distribution-v1":
        errors.append("distribution calibration raw measurements require morpheus-access-distribution-v1")
    if payload.get("evidence_state") != "MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_AND_DISTRIBUTION_BOUND":
        errors.append("distribution calibration raw measurements have unexpected evidence_state")
    n = payload.get("n", payload.get("record_count"))
    operations = payload.get("operations")
    if not isinstance(n, int) or n <= 0:
        errors.append("distribution calibration raw measurements require positive n/record_count")
    if not isinstance(operations, int) or operations <= 0:
        errors.append("distribution calibration raw measurements require positive operations")
    measurements = payload.get("measurements")
    if not isinstance(measurements, list) or not measurements:
        errors.append("distribution calibration measurements must be a non-empty array")
        return tuple(errors)

    seen: set[tuple[str, str, str, str]] = set()
    for index, measurement in enumerate(measurements):
        prefix = f"measurement[{index}]"
        if not isinstance(measurement, dict):
            errors.append(f"{prefix} must be an object")
            continue
        primitive = str(measurement.get("primitive", "")).strip()
        operation = str(measurement.get("operation", "")).strip()
        implementation_id = str(measurement.get("implementation_id", "")).strip()
        if not primitive:
            errors.append(f"{prefix} primitive is required")
        if not operation:
            errors.append(f"{prefix} operation is required")
        if not implementation_id:
            errors.append(f"{prefix} implementation_id is required")
        ns_per_op = measurement.get("ns_per_op")
        repetitions = measurement.get("repetitions", 1)
        if not isinstance(ns_per_op, (int, float)) or ns_per_op <= 0:
            errors.append(f"{prefix} ns_per_op must be positive")
        if not isinstance(repetitions, int) or repetitions <= 0:
            errors.append(f"{prefix} repetitions must be positive")
        errors.extend(_validate_distribution_identity(measurement.get("access_distribution"), prefix=prefix))
        distribution = measurement.get("access_distribution")
        if isinstance(distribution, dict):
            canonical = json.dumps(distribution, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            key = (primitive, implementation_id, operation, canonical)
            if key in seen:
                errors.append(f"{prefix} duplicates primitive/implementation/operation/distribution identity")
            seen.add(key)
    return tuple(errors)


def _validate_distribution_calibration_manifest(payload: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("distribution calibration manifest requires schema_version=1")
    if payload.get("distribution_protocol") != "morpheus-access-distribution-v1":
        errors.append("distribution calibration manifest requires morpheus-access-distribution-v1")
    if payload.get("evidence_state") != "CONTENT_HASHED_DISTRIBUTION_BOUND_PRIMITIVE_CALIBRATION_MATRIX":
        errors.append("distribution calibration manifest has unexpected evidence_state")
    for field in ("machine_profile_sha256", "machine_fingerprint_sha256", "executable_sha256"):
        if not _valid_sha256(payload.get(field)):
            errors.append(f"distribution calibration manifest has invalid {field}")
    if not _valid_git_sha(payload.get("source_commit")):
        errors.append("distribution calibration manifest requires a 40-character source_commit")
    distributions = payload.get("distributions")
    if not isinstance(distributions, list) or not distributions:
        errors.append("distribution calibration manifest distributions must be a non-empty array")
    elif any(item not in _DISTRIBUTION_KINDS for item in distributions):
        errors.append("distribution calibration manifest contains unsupported distribution")
    implementation_ids = payload.get("implementation_ids")
    if not isinstance(implementation_ids, list) or not implementation_ids or any(not str(item).strip() for item in implementation_ids):
        errors.append("distribution calibration manifest implementation_ids must be non-empty")
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        errors.append("distribution calibration manifest runs must be a non-empty array")
        return tuple(errors)
    for index, run in enumerate(runs):
        prefix = f"distribution calibration run[{index}]"
        if not isinstance(run, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not _valid_sha256(run.get("sha256")):
            errors.append(f"{prefix} has invalid sha256")
        if not isinstance(run.get("record_count"), int) or run["record_count"] <= 0:
            errors.append(f"{prefix} requires positive record_count")
        if not isinstance(run.get("operations"), int) or run["operations"] <= 0:
            errors.append(f"{prefix} requires positive operations")
        run_distributions = run.get("distributions")
        if not isinstance(run_distributions, list) or not run_distributions:
            errors.append(f"{prefix} distributions must be non-empty")
        elif isinstance(distributions, list) and sorted(run_distributions) != sorted(distributions):
            errors.append(f"{prefix} distributions differ from manifest distributions")
    return tuple(errors)


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
            "morpheus-distribution-calibration-v1",
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
        if protocol == "morpheus-distribution-calibration-v1":
            errors = _validate_distribution_raw_measurements(payload)
            if errors:
                return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", errors)

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

    if role == "distribution_calibration_manifest":
        errors = _validate_distribution_calibration_manifest(payload)
        if errors:
            return EvidenceValidation(role, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", errors)

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
    """Validate hash and protocol links decidable from packaged artifacts."""

    errors: list[str] = []
    raw = artifacts.get("raw_measurements")
    stats = artifacts.get("statistical_summary")
    if raw is not None and stats is not None:
        raw_payload = raw.get("json")
        stats_payload = stats.get("json")
        if isinstance(raw_payload, dict) and raw_payload.get("protocol") != "morpheus-standard-baseline-matrix-v1":
            errors.append(
                "statistical_summary schema morpheus-standard-baseline-statistics-v1 requires raw_measurements protocol morpheus-standard-baseline-matrix-v1"
            )
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

    distribution_manifest = artifacts.get("distribution_calibration_manifest")
    if distribution_manifest is not None:
        manifest_payload = distribution_manifest.get("json")
        if isinstance(manifest_payload, dict) and machine is not None:
            expected = str(manifest_payload.get("machine_profile_sha256", "")).lower()
            actual = str(machine.get("sha256", "")).lower()
            if expected and actual and expected != actual:
                errors.append(
                    f"distribution_calibration_manifest machine_profile_sha256={expected} does not match packaged machine_profile byte hash={actual}"
                )
        if isinstance(manifest_payload, dict) and raw is not None:
            raw_payload = raw.get("json")
            if not isinstance(raw_payload, dict) or raw_payload.get("protocol") != "morpheus-distribution-calibration-v1":
                errors.append(
                    "distribution_calibration_manifest requires packaged raw_measurements protocol morpheus-distribution-calibration-v1 when raw_measurements is present"
                )
            raw_hash = str(raw.get("sha256", "")).lower()
            run_hashes = {
                str(item.get("sha256", "")).lower()
                for item in manifest_payload.get("runs", [])
                if isinstance(item, dict)
            }
            if raw_hash and raw_hash not in run_hashes:
                errors.append(
                    "packaged distribution raw_measurements byte hash is not referenced by distribution_calibration_manifest runs"
                )
    return errors
