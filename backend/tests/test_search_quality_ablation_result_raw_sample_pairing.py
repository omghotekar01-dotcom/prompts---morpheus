from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_result_raw_sample_pairing import (
    EVIDENCE_STATE,
    PAIRING_KEYS,
    verify_ablation_raw_sample_pairing,
)
from app.search_quality_ablation_result_raw_sample_semantics import (
    RAW_SAMPLE_SCHEMA,
    verify_ablation_raw_sample_semantics,
)
from app.search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding


def _record(sample_id: str, condition_id: str, repetition_index: int, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "schema": RAW_SAMPLE_SCHEMA,
        "sample_id": sample_id,
        "condition_id": condition_id,
        "workload_id": "lookup-heavy",
        "repetition_index": repetition_index,
        "metric": "latency_ns",
        "value": 100 if condition_id == "reference" else 108,
        "measurement_source": "native-benchmark",
        "protocol_id": "ablation-v1",
        "machine_fingerprint": "machine-a",
    }
    record.update(overrides)
    return record


def _jsonl(*records: dict[str, object]) -> bytes:
    return b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        for record in records
    )


RAW = {
    "seed-1337.jsonl": _jsonl(_record("s1", "reference", 0), _record("s2", "ablated", 0)),
    "seed-2027.jsonl": _jsonl(_record("s3", "reference", 1), _record("s4", "ablated", 1)),
}


def _artifact(
    raw_samples: dict[str, bytes] = RAW,
    *,
    pairing_override: dict[str, object] | None = None,
    condition_ids: list[str] | None = None,
) -> bytes:
    inventory = [
        {"artifact_id": artifact_id, "sha256": hashlib.sha256(content).hexdigest()}
        for artifact_id, content in sorted(raw_samples.items())
    ]
    pairing: dict[str, object] = {"pairing_keys": list(PAIRING_KEYS), "complete_pair_count": 2}
    if pairing_override:
        pairing.update(pairing_override)
    return json.dumps(
        {
            "schema": "morpheus.ablation-result/v1",
            "raw_sample_evidence": {
                "inventory_complete": True,
                "artifacts": inventory,
                "semantics": {
                    "schema": RAW_SAMPLE_SCHEMA,
                    "measurement_source": "native-benchmark",
                    "protocol_id": "ablation-v1",
                    "machine_fingerprint": "machine-a",
                    "metric": "latency_ns",
                    "record_count": sum(len([line for line in raw.decode().splitlines() if line.strip()]) for raw in raw_samples.values()),
                    "condition_ids": condition_ids or ["reference", "ablated"],
                },
                "pairing": pairing,
            },
            "automatic_control_allowed": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _p46(result: bytes, raw_samples: dict[str, bytes] = RAW) -> AblationResultRawSampleBinding:
    inventory = [
        {"artifact_id": artifact_id, "sha256": hashlib.sha256(content).hexdigest()}
        for artifact_id, content in sorted(raw_samples.items())
    ]
    inventory_sha = hashlib.sha256(
        json.dumps(inventory, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return AblationResultRawSampleBinding(
        result_artifact_verification_sha256="11" * 32,
        result_artifact_sha256=hashlib.sha256(result).hexdigest(),
        raw_sample_inventory_sha256=inventory_sha,
        raw_sample_artifact_count=len(raw_samples),
        raw_sample_binding_sha256="22" * 32,
        raw_sample_bytes_bound=True,
    )


def _inputs(raw_samples: dict[str, bytes] = RAW, **artifact_kwargs: object):
    result = _artifact(raw_samples, **artifact_kwargs)
    binding = _p46(result, raw_samples)
    semantics = verify_ablation_raw_sample_semantics(
        binding, result_artifact=result, raw_sample_artifacts=raw_samples
    )
    return result, binding, semantics


def test_p48_verifies_complete_pairs_deterministically() -> None:
    result, binding, semantics = _inputs()
    first = verify_ablation_raw_sample_pairing(
        semantics, binding, result_artifact=result, raw_sample_artifacts=RAW
    )
    second = verify_ablation_raw_sample_pairing(
        semantics,
        binding,
        result_artifact=result.decode(),
        raw_sample_artifacts={key: value.decode() for key, value in reversed(list(RAW.items()))},
    )
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.pairing_verified is True
    assert first.complete_pair_count == 2
    assert first.condition_count == 2
    assert first.record_count == 4
    assert first.automatic_control_allowed is False


def test_p48_rejects_duplicate_condition_within_pair() -> None:
    raw = dict(RAW)
    raw["seed-1337.jsonl"] = _jsonl(_record("s1", "reference", 0), _record("s2", "reference", 0))
    result, binding, semantics = _inputs(raw)
    with pytest.raises(ValueError, match="duplicate condition_id"):
        verify_ablation_raw_sample_pairing(semantics, binding, result_artifact=result, raw_sample_artifacts=raw)


def test_p48_rejects_incomplete_or_unexpected_condition_pair() -> None:
    raw = dict(RAW)
    raw["seed-1337.jsonl"] = _jsonl(_record("s1", "reference", 0), _record("s2", "other", 0))
    result, binding, semantics = _inputs(raw, condition_ids=["reference", "ablated", "other"])
    with pytest.raises(ValueError, match="incomplete or unexpected-condition"):
        verify_ablation_raw_sample_pairing(semantics, binding, result_artifact=result, raw_sample_artifacts=raw)


def test_p48_rejects_declared_pair_count_or_keys_drift() -> None:
    result, binding, semantics = _inputs(pairing_override={"complete_pair_count": 3})
    with pytest.raises(ValueError, match="complete_pair_count"):
        verify_ablation_raw_sample_pairing(semantics, binding, result_artifact=result, raw_sample_artifacts=RAW)

    result, binding, semantics = _inputs(pairing_override={"pairing_keys": ["sample_id"]})
    with pytest.raises(ValueError, match="pairing_keys"):
        verify_ablation_raw_sample_pairing(semantics, binding, result_artifact=result, raw_sample_artifacts=RAW)


def test_p48_rejects_boolean_zero_or_missing_pair_count() -> None:
    for value in (True, 0, None):
        result, binding, semantics = _inputs(pairing_override={"complete_pair_count": value})
        with pytest.raises(ValueError, match="complete_pair_count"):
            verify_ablation_raw_sample_pairing(semantics, binding, result_artifact=result, raw_sample_artifacts=RAW)


def test_p48_rejects_incompatible_or_unverified_p47() -> None:
    result, binding, semantics = _inputs()
    with pytest.raises(ValueError, match="incompatible evidence_state"):
        verify_ablation_raw_sample_pairing(
            replace(semantics, evidence_state="OTHER"), binding, result_artifact=result, raw_sample_artifacts=RAW
        )
    with pytest.raises(ValueError, match="must be verified"):
        verify_ablation_raw_sample_pairing(
            replace(semantics, semantics_verified=False), binding, result_artifact=result, raw_sample_artifacts=RAW
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_raw_sample_pairing(
            replace(semantics, automatic_control_allowed=True), binding, result_artifact=result, raw_sample_artifacts=RAW
        )


def test_p48_rejects_semantics_or_exact_byte_drift() -> None:
    result, binding, semantics = _inputs()
    with pytest.raises(ValueError, match="do not match"):
        verify_ablation_raw_sample_pairing(
            replace(semantics, semantic_verification_sha256="33" * 32),
            binding,
            result_artifact=result,
            raw_sample_artifacts=RAW,
        )
    with pytest.raises(ValueError, match="result_artifact bytes"):
        verify_ablation_raw_sample_pairing(
            semantics, binding, result_artifact=result + b" ", raw_sample_artifacts=RAW
        )


def test_p48_rejects_duplicate_pair_caused_across_artifacts() -> None:
    raw = {
        "a.jsonl": _jsonl(_record("s1", "reference", 0), _record("s2", "ablated", 0)),
        "b.jsonl": _jsonl(_record("s3", "reference", 0), _record("s4", "ablated", 1)),
    }
    result, binding, semantics = _inputs(raw)
    with pytest.raises(ValueError, match="duplicate condition_id"):
        verify_ablation_raw_sample_pairing(semantics, binding, result_artifact=result, raw_sample_artifacts=raw)
