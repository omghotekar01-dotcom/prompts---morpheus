from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_result_raw_sample_pairing import PAIRING_KEYS, verify_ablation_raw_sample_pairing
from app.search_quality_ablation_result_raw_sample_pairwise_delta_inventory import (
    EVIDENCE_STATE,
    verify_ablation_raw_sample_pairwise_delta_inventory,
)
from app.search_quality_ablation_result_raw_sample_pairwise_descriptives import verify_ablation_raw_sample_pairwise_descriptives
from app.search_quality_ablation_result_raw_sample_semantics import RAW_SAMPLE_SCHEMA, verify_ablation_raw_sample_semantics
from app.search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding


def _record(sample: str, condition: str, rep: int, value: int) -> dict[str, object]:
    return {
        "schema": RAW_SAMPLE_SCHEMA,
        "sample_id": sample,
        "condition_id": condition,
        "workload_id": "w",
        "repetition_index": rep,
        "metric": "latency_ns",
        "value": value,
        "measurement_source": "native-benchmark",
        "protocol_id": "ablation-v1",
        "machine_fingerprint": "m",
    }


def _jsonl(*rows: dict[str, object]) -> bytes:
    return b"".join(json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n" for row in rows)


RAW = {
    "a.jsonl": _jsonl(_record("s1", "reference", 0, 100), _record("s2", "ablated", 0, 108)),
    "b.jsonl": _jsonl(_record("s3", "reference", 1, 110), _record("s4", "ablated", 1, 114)),
}
PAIR_DELTA_SHA = "9e0dfb2acee45b80c507b8afc24e1f78711fa465dadeb5f87ad04c9732361640"


def _artifact(*, pair_delta_sha: object = PAIR_DELTA_SHA, complete: object = True, comparisons: object = None) -> bytes:
    inventory = [{"artifact_id": key, "sha256": hashlib.sha256(value).hexdigest()} for key, value in sorted(RAW.items())]
    delta_comparisons = comparisons if comparisons is not None else [
        {"condition_id": "ablated", "pair_count": 2, "pair_delta_sha256": pair_delta_sha}
    ]
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
                    "machine_fingerprint": "m",
                    "metric": "latency_ns",
                    "record_count": 4,
                    "condition_ids": ["reference", "ablated"],
                },
                "pairing": {"pairing_keys": list(PAIRING_KEYS), "complete_pair_count": 2},
                "pairwise_descriptives": {
                    "reference_condition_id": "reference",
                    "comparisons": [{"condition_id": "ablated", "pair_count": 2, "mean_delta": "6"}],
                },
                "pairwise_delta_inventory": {
                    "inventory_complete": complete,
                    "comparisons": delta_comparisons,
                },
            },
            "automatic_control_allowed": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _inputs(result: bytes):
    inventory = [{"artifact_id": key, "sha256": hashlib.sha256(value).hexdigest()} for key, value in sorted(RAW.items())]
    inventory_sha = hashlib.sha256(
        json.dumps(inventory, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    binding = AblationResultRawSampleBinding(
        result_artifact_verification_sha256="11" * 32,
        result_artifact_sha256=hashlib.sha256(result).hexdigest(),
        raw_sample_inventory_sha256=inventory_sha,
        raw_sample_artifact_count=2,
        raw_sample_binding_sha256="22" * 32,
        raw_sample_bytes_bound=True,
    )
    semantics = verify_ablation_raw_sample_semantics(binding, result_artifact=result, raw_sample_artifacts=RAW)
    pairing = verify_ablation_raw_sample_pairing(semantics, binding, result_artifact=result, raw_sample_artifacts=RAW)
    descriptives = verify_ablation_raw_sample_pairwise_descriptives(
        pairing, semantics, binding, result_artifact=result, raw_sample_artifacts=RAW
    )
    return binding, semantics, pairing, descriptives


def _verify(result: bytes):
    binding, semantics, pairing, descriptives = _inputs(result)
    return verify_ablation_raw_sample_pairwise_delta_inventory(
        descriptives,
        pairing,
        semantics,
        binding,
        result_artifact=result,
        raw_sample_artifacts=RAW,
    )


def test_p50_verifies_exact_pair_delta_inventory_deterministically() -> None:
    first = _verify(_artifact())
    second = _verify(_artifact(pair_delta_sha=PAIR_DELTA_SHA.upper()))
    assert first.reference_condition_id == "reference"
    assert first.comparison_count == 1 and first.pair_count == 2 and first.delta_record_count == 2
    assert first.evidence_state == EVIDENCE_STATE and first.delta_inventory_verified
    assert not first.automatic_control_allowed
    assert first.delta_inventory_sha256 == second.delta_inventory_sha256


def test_p50_rejects_wrong_pair_delta_hash() -> None:
    with pytest.raises(ValueError, match="does not match raw samples"):
        _verify(_artifact(pair_delta_sha="33" * 32))


@pytest.mark.parametrize("value", ["bad", "3" * 63, True])
def test_p50_rejects_malformed_pair_delta_hash(value: object) -> None:
    with pytest.raises(ValueError, match="pair_delta_sha256"):
        _verify(_artifact(pair_delta_sha=value))


def test_p50_requires_complete_unique_comparison_inventory() -> None:
    with pytest.raises(ValueError, match="inventory_complete"):
        _verify(_artifact(complete=False))
    duplicate = [
        {"condition_id": "ablated", "pair_count": 2, "pair_delta_sha256": PAIR_DELTA_SHA},
        {"condition_id": "ablated", "pair_count": 2, "pair_delta_sha256": PAIR_DELTA_SHA},
    ]
    with pytest.raises(ValueError, match="unique"):
        _verify(_artifact(comparisons=duplicate))


def test_p50_rejects_wrong_pair_count_or_condition_membership() -> None:
    with pytest.raises(ValueError, match="does not match raw samples"):
        _verify(_artifact(comparisons=[{"condition_id": "ablated", "pair_count": 1, "pair_delta_sha256": PAIR_DELTA_SHA}]))
    with pytest.raises(ValueError, match="conditions do not match"):
        _verify(_artifact(comparisons=[{"condition_id": "other", "pair_count": 2, "pair_delta_sha256": PAIR_DELTA_SHA}]))


def test_p50_rejects_incompatible_or_drifted_p49() -> None:
    result = _artifact()
    binding, semantics, pairing, descriptives = _inputs(result)
    with pytest.raises(ValueError, match="incompatible or unverified"):
        verify_ablation_raw_sample_pairwise_delta_inventory(
            replace(descriptives, descriptives_verified=False), pairing, semantics, binding,
            result_artifact=result, raw_sample_artifacts=RAW,
        )
    with pytest.raises(ValueError, match="do not match"):
        verify_ablation_raw_sample_pairwise_delta_inventory(
            replace(descriptives, descriptives_sha256="44" * 32), pairing, semantics, binding,
            result_artifact=result, raw_sample_artifacts=RAW,
        )


def test_p50_rejects_result_or_raw_sample_byte_drift() -> None:
    result = _artifact()
    binding, semantics, pairing, descriptives = _inputs(result)
    with pytest.raises(ValueError):
        verify_ablation_raw_sample_pairwise_delta_inventory(
            descriptives, pairing, semantics, binding,
            result_artifact=result + b" ", raw_sample_artifacts=RAW,
        )
    drifted = dict(RAW)
    drifted["a.jsonl"] = drifted["a.jsonl"] + b"\n"
    with pytest.raises(ValueError):
        verify_ablation_raw_sample_pairwise_delta_inventory(
            descriptives, pairing, semantics, binding,
            result_artifact=result, raw_sample_artifacts=drifted,
        )
