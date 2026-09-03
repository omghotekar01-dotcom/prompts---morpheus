"""Raw-sample artifact binding for byte-verified MORPHEUS ablation results.

P45 establishes that a bound result reports artifact identities consistent with supplied byte-verified
research provenance. This P46 gate additionally requires the same result bytes to declare a complete
inventory of caller-supplied raw-sample artifacts and verifies each declared SHA-256 against the exact
bytes supplied to this verifier.

This is internal evidence-linkage methodology only. It does not prove that supplied bytes are genuine
measurements, that they were emitted by the bound implementation, or that sample collection was valid,
independent, representative, complete outside the declared inventory, or independently reproduced.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .search_quality_ablation_result_artifact_verification import (
    EVIDENCE_STATE as RESULT_ARTIFACT_VERIFICATION_EVIDENCE_STATE,
    AblationResultArtifactVerificationConsistency,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RESULT_RAW_SAMPLE_BINDING"
TRUTH_BOUNDARY = (
    "This gate proves only that one P45-verified result artifact declares a complete inventory of the caller-supplied "
    "raw-sample artifacts presented to this verifier and that every declared SHA-256 matches those exact supplied bytes. "
    "It does not prove that the bytes are genuine measurements, that the bound implementation produced them, that the "
    "collection process was valid or independent, that the samples are representative, that no samples or analyses exist "
    "outside the declared inventory, or that another party reproduced the result. Passing establishes no measurement "
    "validity, causal validity, benchmark/search superiority, publication-grade evidence, novelty, patentability, "
    "production readiness, or automatic-control authorization."
)


def _validated_hex(name: str, value: object, length: int = 64) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a hexadecimal string")
    normalized = value.strip().casefold()
    if len(normalized) != length or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{name} must be a {length}-character hexadecimal digest")
    return normalized


def _normalized_nonempty(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _raw_bytes(name: str, value: object) -> bytes:
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bytes):
        raw = value
    else:
        raise TypeError(f"raw sample artifact {name!r} must be bytes or str")
    if not raw:
        raise ValueError(f"raw sample artifact {name!r} cannot be empty")
    return raw


def _json_object(result_artifact: bytes | str) -> tuple[bytes, dict[str, Any]]:
    if isinstance(result_artifact, str):
        raw = result_artifact.encode("utf-8")
    elif isinstance(result_artifact, bytes):
        raw = result_artifact
    else:
        raise TypeError("result_artifact must be bytes or str")
    if not raw:
        raise ValueError("result_artifact cannot be empty")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("result_artifact JSON must be an object")
    return raw, value


@dataclass(frozen=True)
class AblationResultRawSampleBinding:
    result_artifact_verification_sha256: str
    result_artifact_sha256: str
    raw_sample_inventory_sha256: str
    raw_sample_artifact_count: int
    raw_sample_binding_sha256: str
    raw_sample_bytes_bound: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "result_artifact_verification_sha256": self.result_artifact_verification_sha256,
            "result_artifact_sha256": self.result_artifact_sha256,
            "raw_sample_inventory_sha256": self.raw_sample_inventory_sha256,
            "raw_sample_artifact_count": self.raw_sample_artifact_count,
            "raw_sample_binding_sha256": self.raw_sample_binding_sha256,
            "raw_sample_bytes_bound": self.raw_sample_bytes_bound,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def bind_ablation_result_raw_samples(
    result_verification: AblationResultArtifactVerificationConsistency,
    *,
    result_artifact: bytes | str,
    raw_sample_artifacts: Mapping[str, bytes | str],
) -> AblationResultRawSampleBinding:
    """Fail closed unless P45-bound result bytes exactly inventory all supplied raw-sample bytes."""

    if result_verification.evidence_state != RESULT_ARTIFACT_VERIFICATION_EVIDENCE_STATE:
        raise ValueError("result artifact verification has an incompatible evidence_state")
    if result_verification.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not result_verification.artifact_byte_consistency_verified:
        raise ValueError("P45 artifact-byte consistency must be verified before raw-sample binding")

    expected_result_sha = _validated_hex("result_artifact_sha256", result_verification.result_artifact_sha256)
    result_verification_sha = _validated_hex(
        "result_artifact_verification_sha256", result_verification.result_artifact_verification_sha256
    )

    raw_result, document = _json_object(result_artifact)
    actual_result_sha = hashlib.sha256(raw_result).hexdigest()
    if actual_result_sha != expected_result_sha:
        raise ValueError("result_artifact bytes do not match the P45 result_artifact_sha256")
    if document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must explicitly set automatic_control_allowed to false")

    if not isinstance(raw_sample_artifacts, Mapping):
        raise TypeError("raw_sample_artifacts must be a mapping")
    if not raw_sample_artifacts:
        raise ValueError("raw_sample_artifacts cannot be empty")

    supplied: dict[str, str] = {}
    for artifact_id, content in raw_sample_artifacts.items():
        normalized_id = _normalized_nonempty("raw sample artifact_id", artifact_id)
        if normalized_id in supplied:
            raise ValueError("raw_sample_artifacts contains duplicate normalized artifact_id values")
        supplied[normalized_id] = hashlib.sha256(_raw_bytes(normalized_id, content)).hexdigest()

    declaration = document.get("raw_sample_evidence")
    if not isinstance(declaration, dict):
        raise ValueError("result artifact raw_sample_evidence must be an object")
    if declaration.get("inventory_complete") is not True:
        raise ValueError("result artifact must explicitly declare raw_sample_evidence.inventory_complete=true")
    declared_artifacts = declaration.get("artifacts")
    if not isinstance(declared_artifacts, list) or not declared_artifacts:
        raise ValueError("raw_sample_evidence.artifacts must be a non-empty list")

    declared: dict[str, str] = {}
    for index, item in enumerate(declared_artifacts):
        if not isinstance(item, dict):
            raise ValueError(f"raw_sample_evidence.artifacts[{index}] must be an object")
        artifact_id = _normalized_nonempty(
            f"raw_sample_evidence.artifacts[{index}].artifact_id", item.get("artifact_id")
        )
        if artifact_id in declared:
            raise ValueError("raw_sample_evidence.artifacts contains duplicate artifact_id values")
        declared[artifact_id] = _validated_hex(
            f"raw_sample_evidence.artifacts[{index}].sha256", item.get("sha256")
        )

    if set(declared) != set(supplied):
        missing = sorted(set(supplied) - set(declared))
        unknown = sorted(set(declared) - set(supplied))
        raise ValueError(f"raw-sample inventory mismatch: missing={missing}, unknown={unknown}")
    for artifact_id, supplied_sha in supplied.items():
        if declared[artifact_id] != supplied_sha:
            raise ValueError(f"raw-sample SHA-256 mismatch for artifact_id {artifact_id!r}")

    inventory = [
        {"artifact_id": artifact_id, "sha256": supplied[artifact_id]}
        for artifact_id in sorted(supplied)
    ]
    inventory_bytes = json.dumps(inventory, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    inventory_sha = hashlib.sha256(inventory_bytes).hexdigest()
    binding_payload = {
        "result_artifact_verification_sha256": result_verification_sha,
        "result_artifact_sha256": actual_result_sha,
        "raw_sample_inventory_sha256": inventory_sha,
        "raw_sample_artifact_count": len(inventory),
    }
    binding_bytes = json.dumps(binding_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

    return AblationResultRawSampleBinding(
        result_artifact_verification_sha256=result_verification_sha,
        result_artifact_sha256=actual_result_sha,
        raw_sample_inventory_sha256=inventory_sha,
        raw_sample_artifact_count=len(inventory),
        raw_sample_binding_sha256=hashlib.sha256(binding_bytes).hexdigest(),
        raw_sample_bytes_bound=True,
    )
