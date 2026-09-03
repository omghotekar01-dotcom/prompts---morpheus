"""Pair-completeness verification for P47-semantic MORPHEUS ablation raw samples.

P47 verifies byte-bound JSONL structure and measurement context. P48 additionally verifies the frozen
paired-comparison discipline: every declared (workload_id, repetition_index) pair contains exactly one
sample for every declared condition, with no duplicate condition observation inside a pair.

This is an internal evidence-integrity gate. Pair completeness does not make the samples genuine,
independent, representative, unbiased, correctly instrumented, or causally interpretable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .search_quality_ablation_result_raw_sample_semantics import (
    EVIDENCE_STATE as SEMANTIC_EVIDENCE_STATE,
    AblationRawSampleSemanticConsistency,
    verify_ablation_raw_sample_semantics,
)
from .search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_PAIR_COMPLETENESS"
PAIRING_KEYS = ("workload_id", "repetition_index")
TRUTH_BOUNDARY = (
    "This gate proves only that the exact P46/P47-bound caller-supplied records form complete declared-condition "
    "pairs under (workload_id, repetition_index), with one record per condition in each pair. It does not prove "
    "that records are genuine measurements, that pairing variables capture every dependence, that collection was "
    "independent, randomized, representative, unbiased or correctly instrumented, that excluded/undisclosed samples "
    "do not exist, that the bound implementation emitted the records, or that another party reproduced the experiment. "
    "Passing establishes no causal validity, benchmark/search superiority, publication-grade evidence, novelty, "
    "patentability, production readiness, or automatic-control authorization."
)


def _raw_bytes(name: str, value: object) -> bytes:
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bytes):
        raw = value
    else:
        raise TypeError(f"{name} must be bytes or str")
    if not raw:
        raise ValueError(f"{name} cannot be empty")
    return raw


def _normalized_nonempty(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _strict_nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


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


@dataclass(frozen=True)
class AblationRawSamplePairingConsistency:
    semantic_verification_sha256: str
    raw_sample_inventory_sha256: str
    pairing_context_sha256: str
    pairing_verification_sha256: str
    complete_pair_count: int
    condition_count: int
    record_count: int
    pairing_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "semantic_verification_sha256": self.semantic_verification_sha256,
            "raw_sample_inventory_sha256": self.raw_sample_inventory_sha256,
            "pairing_context_sha256": self.pairing_context_sha256,
            "pairing_verification_sha256": self.pairing_verification_sha256,
            "complete_pair_count": self.complete_pair_count,
            "condition_count": self.condition_count,
            "record_count": self.record_count,
            "pairing_verified": self.pairing_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_raw_sample_pairing(
    semantics: AblationRawSampleSemanticConsistency,
    raw_sample_binding: AblationResultRawSampleBinding,
    *,
    result_artifact: bytes | str,
    raw_sample_artifacts: Mapping[str, bytes | str],
) -> AblationRawSamplePairingConsistency:
    """Fail closed unless exact P47-semantic records satisfy declared paired-comparison completeness."""

    if semantics.evidence_state != SEMANTIC_EVIDENCE_STATE:
        raise ValueError("raw-sample semantics have an incompatible evidence_state")
    if semantics.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not semantics.semantics_verified:
        raise ValueError("P47 raw-sample semantics must be verified before pairing verification")

    recomputed = verify_ablation_raw_sample_semantics(
        raw_sample_binding,
        result_artifact=result_artifact,
        raw_sample_artifacts=raw_sample_artifacts,
    )
    if recomputed != semantics:
        raise ValueError("supplied P47 semantics do not match the exact result/raw-sample bytes")

    _, document = _json_object(result_artifact)
    if document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must explicitly set automatic_control_allowed to false")
    evidence = document.get("raw_sample_evidence")
    if not isinstance(evidence, dict):
        raise ValueError("result artifact raw_sample_evidence must be an object")
    semantic_doc = evidence.get("semantics")
    if not isinstance(semantic_doc, dict):
        raise ValueError("result artifact raw_sample_evidence.semantics must be an object")
    declared_conditions = semantic_doc.get("condition_ids")
    if not isinstance(declared_conditions, list) or not declared_conditions:
        raise ValueError("condition_ids must be a non-empty list")
    conditions = tuple(_normalized_nonempty("condition_id", value) for value in declared_conditions)
    if len(set(conditions)) != len(conditions):
        raise ValueError("condition_ids must not contain duplicates after normalization")

    pairing = evidence.get("pairing")
    if not isinstance(pairing, dict):
        raise ValueError("result artifact raw_sample_evidence.pairing must be an object")
    keys = pairing.get("pairing_keys")
    if not isinstance(keys, list) or tuple(keys) != PAIRING_KEYS:
        raise ValueError(f"pairing_keys must equal {list(PAIRING_KEYS)!r}")
    expected_pair_count = _strict_nonnegative_int("complete_pair_count", pairing.get("complete_pair_count"))
    if expected_pair_count == 0:
        raise ValueError("complete_pair_count must be greater than zero")

    pairs: dict[tuple[str, int], set[str]] = {}
    record_count = 0
    for artifact_id, content in raw_sample_artifacts.items():
        raw = _raw_bytes(_normalized_nonempty("artifact_id", artifact_id), content)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"raw sample artifact {artifact_id!r} must be UTF-8 JSONL") from exc
        for line_number, line in enumerate((line for line in text.splitlines() if line.strip()), start=1):
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"raw sample artifact {artifact_id!r} line {line_number} must be a JSON object")
            workload = _normalized_nonempty("workload_id", record.get("workload_id"))
            repetition = _strict_nonnegative_int("repetition_index", record.get("repetition_index"))
            condition = _normalized_nonempty("condition_id", record.get("condition_id"))
            key = (workload, repetition)
            observed = pairs.setdefault(key, set())
            if condition in observed:
                raise ValueError(f"pair {key!r} contains duplicate condition_id {condition!r}")
            observed.add(condition)
            record_count += 1

    expected_conditions = set(conditions)
    incomplete = [key for key, observed in pairs.items() if observed != expected_conditions]
    if incomplete:
        raise ValueError("raw samples contain an incomplete or unexpected-condition pair")
    if len(pairs) != expected_pair_count:
        raise ValueError("complete_pair_count does not match observed complete pairs")
    if record_count != expected_pair_count * len(conditions):
        raise ValueError("paired record count is inconsistent with pair and condition counts")
    if record_count != semantics.raw_sample_record_count:
        raise ValueError("paired record count does not match P47 semantic record count")

    canonical_pairs = [
        {"workload_id": workload, "repetition_index": repetition, "condition_ids": sorted(pairs[(workload, repetition)])}
        for workload, repetition in sorted(pairs)
    ]
    context_payload = {
        "pairing_keys": list(PAIRING_KEYS),
        "complete_pair_count": len(pairs),
        "condition_ids": sorted(expected_conditions),
        "pairs": canonical_pairs,
    }
    context_bytes = json.dumps(context_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    context_sha = hashlib.sha256(context_bytes).hexdigest()
    verification_payload = {
        "semantic_verification_sha256": _validated_hex("semantic_verification_sha256", semantics.semantic_verification_sha256),
        "raw_sample_inventory_sha256": _validated_hex("raw_sample_inventory_sha256", semantics.raw_sample_inventory_sha256),
        "pairing_context_sha256": context_sha,
    }
    verification_sha = hashlib.sha256(
        json.dumps(verification_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return AblationRawSamplePairingConsistency(
        semantic_verification_sha256=verification_payload["semantic_verification_sha256"],
        raw_sample_inventory_sha256=verification_payload["raw_sample_inventory_sha256"],
        pairing_context_sha256=context_sha,
        pairing_verification_sha256=verification_sha,
        complete_pair_count=len(pairs),
        condition_count=len(conditions),
        record_count=record_count,
        pairing_verified=True,
    )
