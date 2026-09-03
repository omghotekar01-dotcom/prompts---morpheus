from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_result_raw_sample_semantics import (
    EVIDENCE_STATE,
    RAW_SAMPLE_SCHEMA,
    verify_ablation_raw_sample_semantics,
)
from app.search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding


def _record(sample_id: str, condition_id: str, *, value: object = 101, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "schema": RAW_SAMPLE_SCHEMA,
        "sample_id": sample_id,
        "condition_id": condition_id,
        "workload_id": "lookup-heavy",
        "repetition_index": 0,
        "metric": "latency_ns",
        "value": value,
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
    "seed-1337.jsonl": _jsonl(_record("s1", "reference"), _record("s2", "ablated", value=109)),
    "seed-2027.jsonl": _jsonl(_record("s3", "reference", value=99), _record("s4", "ablated", value=107)),
}


def _artifact(*, raw_samples: dict[str, bytes] = RAW, semantics_override: dict[str, object] | None = None) -> bytes:
    semantics: dict[str, object] = {
        "schema": RAW_SAMPLE_SCHEMA,
        "measurement_source": "native-benchmark",
        "protocol_id": "ablation-v1",
        "machine_fingerprint": "machine-a",
        "metric": "latency_ns",
        "record_count": 4,
        "condition_ids": ["reference", "ablated"],
    }
    if semantics_override:
        semantics.update(semantics_override)
    inventory = [
        {"artifact_id": artifact_id, "sha256": hashlib.sha256(content).hexdigest()}
        for artifact_id, content in sorted(raw_samples.items())
    ]
    return json.dumps(
        {
            "schema": "morpheus.ablation-result/v1",
            "raw_sample_evidence": {"inventory_complete": True, "artifacts": inventory, "semantics": semantics},
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


def test_p47_verifies_bound_jsonl_semantics_deterministically() -> None:
    result = _artifact()
    first = verify_ablation_raw_sample_semantics(_p46(result), result_artifact=result, raw_sample_artifacts=RAW)
    second = verify_ablation_raw_sample_semantics(
        _p46(result),
        result_artifact=result.decode(),
        raw_sample_artifacts={key: value.decode() for key, value in reversed(list(RAW.items()))},
    )
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.semantics_verified is True
    assert first.raw_sample_record_count == 4
    assert first.raw_sample_artifact_count == 2
    assert first.condition_count == 2
    assert first.automatic_control_allowed is False


def test_p47_rejects_byte_inventory_drift() -> None:
    result = _artifact()
    changed = dict(RAW)
    changed["seed-1337.jsonl"] += _jsonl(_record("s5", "reference"))
    with pytest.raises(ValueError, match="inventory does not match"):
        verify_ablation_raw_sample_semantics(_p46(result), result_artifact=result, raw_sample_artifacts=changed)


def test_p47_rejects_invalid_jsonl_or_non_object_records() -> None:
    bad = dict(RAW)
    bad["seed-1337.jsonl"] = b"not-json\n"
    result = _artifact(raw_samples=bad)
    with pytest.raises(ValueError, match="invalid JSON"):
        verify_ablation_raw_sample_semantics(_p46(result, bad), result_artifact=result, raw_sample_artifacts=bad)

    bad = dict(RAW)
    bad["seed-1337.jsonl"] = b"[]\n"
    result = _artifact(raw_samples=bad)
    with pytest.raises(ValueError, match="must be a JSON object"):
        verify_ablation_raw_sample_semantics(_p46(result, bad), result_artifact=result, raw_sample_artifacts=bad)


def test_p47_rejects_schema_and_measurement_context_drift() -> None:
    bad = dict(RAW)
    bad["seed-1337.jsonl"] = _jsonl(_record("s1", "reference", schema="other"), _record("s2", "ablated"))
    result = _artifact(raw_samples=bad)
    with pytest.raises(ValueError, match="incompatible schema"):
        verify_ablation_raw_sample_semantics(_p46(result, bad), result_artifact=result, raw_sample_artifacts=bad)

    bad = dict(RAW)
    bad["seed-1337.jsonl"] = _jsonl(
        _record("s1", "reference", protocol_id="other"), _record("s2", "ablated")
    )
    result = _artifact(raw_samples=bad)
    with pytest.raises(ValueError, match="measurement context"):
        verify_ablation_raw_sample_semantics(_p46(result, bad), result_artifact=result, raw_sample_artifacts=bad)


def test_p47_rejects_record_count_and_condition_coverage_drift() -> None:
    result = _artifact(semantics_override={"record_count": 5})
    with pytest.raises(ValueError, match="record_count"):
        verify_ablation_raw_sample_semantics(_p46(result), result_artifact=result, raw_sample_artifacts=RAW)

    result = _artifact(semantics_override={"condition_ids": ["reference", "different"]})
    with pytest.raises(ValueError, match="condition coverage"):
        verify_ablation_raw_sample_semantics(_p46(result), result_artifact=result, raw_sample_artifacts=RAW)


def test_p47_rejects_duplicate_sample_ids_and_nonfinite_or_boolean_values() -> None:
    bad = dict(RAW)
    bad["seed-1337.jsonl"] = _jsonl(_record("s1", "reference"), _record("s1", "ablated"))
    result = _artifact(raw_samples=bad)
    with pytest.raises(ValueError, match="duplicate sample_id"):
        verify_ablation_raw_sample_semantics(_p46(result, bad), result_artifact=result, raw_sample_artifacts=bad)

    for value in (True, float("inf")):
        bad = dict(RAW)
        bad["seed-1337.jsonl"] = _jsonl(_record("s1", "reference", value=value), _record("s2", "ablated"))
        result = _artifact(raw_samples=bad)
        with pytest.raises(ValueError, match="finite number"):
            verify_ablation_raw_sample_semantics(_p46(result, bad), result_artifact=result, raw_sample_artifacts=bad)


def test_p47_rejects_incompatible_or_unbound_p46_and_result_byte_drift() -> None:
    result = _artifact()
    report = _p46(result)
    with pytest.raises(ValueError, match="incompatible evidence_state"):
        verify_ablation_raw_sample_semantics(
            replace(report, evidence_state="OTHER"), result_artifact=result, raw_sample_artifacts=RAW
        )
    with pytest.raises(ValueError, match="must be bound"):
        verify_ablation_raw_sample_semantics(
            replace(report, raw_sample_bytes_bound=False), result_artifact=result, raw_sample_artifacts=RAW
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_raw_sample_semantics(
            replace(report, automatic_control_allowed=True), result_artifact=result, raw_sample_artifacts=RAW
        )
    with pytest.raises(ValueError, match="result_artifact bytes"):
        verify_ablation_raw_sample_semantics(report, result_artifact=result + b" ", raw_sample_artifacts=RAW)


def test_p47_rejects_invalid_semantic_declaration_types() -> None:
    result = _artifact(semantics_override={"record_count": True})
    with pytest.raises(ValueError, match="non-negative integer"):
        verify_ablation_raw_sample_semantics(_p46(result), result_artifact=result, raw_sample_artifacts=RAW)

    result = _artifact(semantics_override={"condition_ids": ["reference", " reference "]})
    with pytest.raises(ValueError, match="duplicates"):
        verify_ablation_raw_sample_semantics(_p46(result), result_artifact=result, raw_sample_artifacts=RAW)
