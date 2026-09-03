"""Semantic consistency verification for P46-bound MORPHEUS ablation raw samples.

P46 proves only byte-level inventory agreement between a result artifact and caller-supplied raw-sample
artifacts. P47 additionally verifies that those same bytes are parseable versioned JSONL measurement
records whose declared measurement context and condition coverage agree with the byte-bound result.

This remains internal research-evidence methodology. Structural and contextual consistency does not prove
that records are genuine measurements, independently collected, representative, unbiased, complete beyond
the supplied inventory, or produced by the bound implementation.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping

from .search_quality_ablation_result_raw_samples import (
    EVIDENCE_STATE as RAW_SAMPLE_BINDING_EVIDENCE_STATE,
    AblationResultRawSampleBinding,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_SEMANTICS"
RAW_SAMPLE_SCHEMA = "morpheus.ablation-raw-sample/v1"
TRUTH_BOUNDARY = (
    "This gate proves only that the exact caller-supplied raw-sample bytes already bound by P46 decode as "
    "versioned JSONL records and agree with the result artifact's declared sample count, measurement context, "
    "and condition coverage. It does not prove that any record is a genuine measurement, that collection was "
    "valid, independent, representative or unbiased, that the supplied inventory is globally complete, that the "
    "bound implementation emitted the records, or that another party reproduced the experiment. Passing establishes "
    "no causal validity, benchmark/search superiority, publication-grade evidence, novelty, patentability, production "
    "readiness, or automatic-control authorization."
)


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


def _normalized_nonempty(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _validated_hex(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a hexadecimal string")
    normalized = value.strip().casefold()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{name} must be a 64-character hexadecimal digest")
    return normalized


def _json_object(result_artifact: bytes | str) -> tuple[bytes, dict[str, Any]]:
    raw = _raw_bytes("result_artifact", result_artifact)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("result_artifact JSON must be an object")
    return raw, value


def _strict_nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be a finite number")
    return numeric


@dataclass(frozen=True)
class AblationRawSampleSemanticConsistency:
    raw_sample_binding_sha256: str
    raw_sample_inventory_sha256: str
    semantic_context_sha256: str
    semantic_verification_sha256: str
    raw_sample_artifact_count: int
    raw_sample_record_count: int
    condition_count: int
    semantics_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "raw_sample_binding_sha256": self.raw_sample_binding_sha256,
            "raw_sample_inventory_sha256": self.raw_sample_inventory_sha256,
            "semantic_context_sha256": self.semantic_context_sha256,
            "semantic_verification_sha256": self.semantic_verification_sha256,
            "raw_sample_artifact_count": self.raw_sample_artifact_count,
            "raw_sample_record_count": self.raw_sample_record_count,
            "condition_count": self.condition_count,
            "semantics_verified": self.semantics_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_raw_sample_semantics(
    raw_sample_binding: AblationResultRawSampleBinding,
    *,
    result_artifact: bytes | str,
    raw_sample_artifacts: Mapping[str, bytes | str],
) -> AblationRawSampleSemanticConsistency:
    """Fail closed unless P46-bound raw-sample bytes satisfy the declared JSONL semantics."""

    if raw_sample_binding.evidence_state != RAW_SAMPLE_BINDING_EVIDENCE_STATE:
        raise ValueError("raw-sample binding has an incompatible evidence_state")
    if raw_sample_binding.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not raw_sample_binding.raw_sample_bytes_bound:
        raise ValueError("P46 raw-sample bytes must be bound before semantic verification")

    raw_result, document = _json_object(result_artifact)
    if hashlib.sha256(raw_result).hexdigest() != _validated_hex(
        "result_artifact_sha256", raw_sample_binding.result_artifact_sha256
    ):
        raise ValueError("result_artifact bytes do not match the P46 result_artifact_sha256")
    if document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must explicitly set automatic_control_allowed to false")

    if not isinstance(raw_sample_artifacts, Mapping) or not raw_sample_artifacts:
        raise ValueError("raw_sample_artifacts must be a non-empty mapping")

    supplied: dict[str, bytes] = {}
    for artifact_id, content in raw_sample_artifacts.items():
        normalized_id = _normalized_nonempty("raw sample artifact_id", artifact_id)
        if normalized_id in supplied:
            raise ValueError("raw_sample_artifacts contains duplicate normalized artifact_id values")
        supplied[normalized_id] = _raw_bytes(normalized_id, content)

    inventory = [
        {"artifact_id": artifact_id, "sha256": hashlib.sha256(supplied[artifact_id]).hexdigest()}
        for artifact_id in sorted(supplied)
    ]
    inventory_bytes = json.dumps(inventory, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    inventory_sha = hashlib.sha256(inventory_bytes).hexdigest()
    if inventory_sha != _validated_hex("raw_sample_inventory_sha256", raw_sample_binding.raw_sample_inventory_sha256):
        raise ValueError("supplied raw-sample inventory does not match the P46 binding")
    if len(inventory) != raw_sample_binding.raw_sample_artifact_count:
        raise ValueError("raw-sample artifact count does not match the P46 binding")

    declaration = document.get("raw_sample_evidence")
    if not isinstance(declaration, dict):
        raise ValueError("result artifact raw_sample_evidence must be an object")
    semantics = declaration.get("semantics")
    if not isinstance(semantics, dict):
        raise ValueError("result artifact raw_sample_evidence.semantics must be an object")

    expected_schema = _normalized_nonempty("raw sample schema", semantics.get("schema"))
    if expected_schema != RAW_SAMPLE_SCHEMA:
        raise ValueError(f"raw sample schema must be {RAW_SAMPLE_SCHEMA!r}")
    expected_source = _normalized_nonempty("measurement_source", semantics.get("measurement_source"))
    expected_protocol = _normalized_nonempty("protocol_id", semantics.get("protocol_id"))
    expected_machine = _normalized_nonempty("machine_fingerprint", semantics.get("machine_fingerprint"))
    expected_metric = _normalized_nonempty("metric", semantics.get("metric"))
    expected_count = _strict_nonnegative_int("record_count", semantics.get("record_count"))
    if expected_count == 0:
        raise ValueError("record_count must be greater than zero")
    declared_conditions = semantics.get("condition_ids")
    if not isinstance(declared_conditions, list) or not declared_conditions:
        raise ValueError("condition_ids must be a non-empty list")
    expected_conditions = {_normalized_nonempty("condition_id", value) for value in declared_conditions}
    if len(expected_conditions) != len(declared_conditions):
        raise ValueError("condition_ids must not contain duplicates after normalization")

    seen_sample_ids: set[str] = set()
    observed_conditions: set[str] = set()
    record_count = 0
    for artifact_id in sorted(supplied):
        try:
            text = supplied[artifact_id].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"raw sample artifact {artifact_id!r} must be UTF-8 JSONL") from exc
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            raise ValueError(f"raw sample artifact {artifact_id!r} contains no JSONL records")
        for line_number, line in enumerate(lines, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"raw sample artifact {artifact_id!r} line {line_number} is invalid JSON") from exc
            if not isinstance(record, dict):
                raise ValueError(f"raw sample artifact {artifact_id!r} line {line_number} must be a JSON object")
            if record.get("schema") != expected_schema:
                raise ValueError(f"raw sample artifact {artifact_id!r} line {line_number} has incompatible schema")
            sample_id = _normalized_nonempty("sample_id", record.get("sample_id"))
            if sample_id in seen_sample_ids:
                raise ValueError(f"duplicate sample_id {sample_id!r}")
            seen_sample_ids.add(sample_id)
            condition_id = _normalized_nonempty("condition_id", record.get("condition_id"))
            observed_conditions.add(condition_id)
            _normalized_nonempty("workload_id", record.get("workload_id"))
            _strict_nonnegative_int("repetition_index", record.get("repetition_index"))
            metric = _normalized_nonempty("metric", record.get("metric"))
            _finite_number("value", record.get("value"))
            source = _normalized_nonempty("measurement_source", record.get("measurement_source"))
            protocol = _normalized_nonempty("protocol_id", record.get("protocol_id"))
            machine = _normalized_nonempty("machine_fingerprint", record.get("machine_fingerprint"))
            if (source, protocol, machine, metric) != (
                expected_source,
                expected_protocol,
                expected_machine,
                expected_metric,
            ):
                raise ValueError("raw sample record measurement context does not match result declaration")
            record_count += 1

    if record_count != expected_count:
        raise ValueError("raw sample record_count does not match result declaration")
    if observed_conditions != expected_conditions:
        raise ValueError("raw sample condition coverage does not match result declaration")

    context_payload = {
        "schema": expected_schema,
        "measurement_source": expected_source,
        "protocol_id": expected_protocol,
        "machine_fingerprint": expected_machine,
        "metric": expected_metric,
        "record_count": record_count,
        "condition_ids": sorted(expected_conditions),
    }
    context_bytes = json.dumps(context_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    context_sha = hashlib.sha256(context_bytes).hexdigest()
    verification_payload = {
        "raw_sample_binding_sha256": _validated_hex("raw_sample_binding_sha256", raw_sample_binding.raw_sample_binding_sha256),
        "raw_sample_inventory_sha256": inventory_sha,
        "semantic_context_sha256": context_sha,
    }
    verification_bytes = json.dumps(
        verification_payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return AblationRawSampleSemanticConsistency(
        raw_sample_binding_sha256=verification_payload["raw_sample_binding_sha256"],
        raw_sample_inventory_sha256=inventory_sha,
        semantic_context_sha256=context_sha,
        semantic_verification_sha256=hashlib.sha256(verification_bytes).hexdigest(),
        raw_sample_artifact_count=len(inventory),
        raw_sample_record_count=record_count,
        condition_count=len(expected_conditions),
        semantics_verified=True,
    )
