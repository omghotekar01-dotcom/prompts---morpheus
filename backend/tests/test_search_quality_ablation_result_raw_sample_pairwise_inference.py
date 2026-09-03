from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_result_raw_sample_pairing import PAIRING_KEYS, verify_ablation_raw_sample_pairing
from app.search_quality_ablation_result_raw_sample_pairwise_delta_inventory import verify_ablation_raw_sample_pairwise_delta_inventory
from app.search_quality_ablation_result_raw_sample_pairwise_descriptives import verify_ablation_raw_sample_pairwise_descriptives
from app.search_quality_ablation_result_raw_sample_pairwise_inference import (
    EVIDENCE_STATE,
    verify_ablation_raw_sample_pairwise_inference,
)
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


def _comparison(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "condition_id": "ablated",
        "pair_count": 2,
        "wins": 2,
        "ties": 0,
        "losses": 0,
        "mean_delta": "6",
        "median_delta": "6.0",
        "paired_effect_dz": "2.1213203435596424",
        "exact_sign_test_p_two_sided": "0.5",
        "bootstrap_mean_delta_ci": ["4", "8"],
    }
    item.update(overrides)
    return item


def _artifact(*, inference_overrides: dict[str, object] | None = None, comparisons: object = None) -> bytes:
    inventory = [{"artifact_id": key, "sha256": hashlib.sha256(value).hexdigest()} for key, value in sorted(RAW.items())]
    inference: dict[str, object] = {
        "analysis_complete": True,
        "delta_orientation": "condition_minus_reference",
        "bootstrap_rounds": 1000,
        "bootstrap_seed": 1337,
        "bootstrap_confidence": "0.95",
        "tie_tolerance": "0.000000000001",
        "comparisons": comparisons if comparisons is not None else [_comparison()],
    }
    if inference_overrides:
        inference.update(inference_overrides)
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
                    "inventory_complete": True,
                    "comparisons": [
                        {"condition_id": "ablated", "pair_count": 2, "pair_delta_sha256": PAIR_DELTA_SHA}
                    ],
                },
                "pairwise_inference": inference,
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
    delta_inventory = verify_ablation_raw_sample_pairwise_delta_inventory(
        descriptives, pairing, semantics, binding, result_artifact=result, raw_sample_artifacts=RAW
    )
    return binding, semantics, pairing, descriptives, delta_inventory


def _verify(result: bytes):
    binding, semantics, pairing, descriptives, delta_inventory = _inputs(result)
    return verify_ablation_raw_sample_pairwise_inference(
        delta_inventory,
        descriptives,
        pairing,
        semantics,
        binding,
        result_artifact=result,
        raw_sample_artifacts=RAW,
    )


def test_p51_verifies_protocol_required_paired_inference_deterministically() -> None:
    first = _verify(_artifact())
    second = _verify(_artifact(comparisons=[_comparison(mean_delta="6.000", exact_sign_test_p_two_sided=0.5)]))
    assert first.reference_condition_id == "reference"
    assert first.comparison_count == 1 and first.pair_count == 2
    assert first.bootstrap_rounds == 1000 and first.bootstrap_seed == 1337
    assert first.bootstrap_confidence == "0.95"
    assert first.evidence_state == EVIDENCE_STATE and first.inference_verified
    assert not first.automatic_control_allowed
    assert first.inference_sha256 == second.inference_sha256


@pytest.mark.parametrize(
    "field,value",
    [
        ("wins", 1),
        ("ties", 1),
        ("losses", 1),
        ("mean_delta", "5"),
        ("median_delta", "5"),
        ("paired_effect_dz", "2"),
        ("exact_sign_test_p_two_sided", "0.25"),
        ("bootstrap_mean_delta_ci", ["5", "8"]),
    ],
)
def test_p51_rejects_inference_drift(field: str, value: object) -> None:
    with pytest.raises(ValueError, match="does not match raw samples"):
        _verify(_artifact(comparisons=[_comparison(**{field: value})]))


def test_p51_rejects_wrong_condition_membership_or_duplicates() -> None:
    with pytest.raises(ValueError, match="conditions do not match"):
        _verify(_artifact(comparisons=[_comparison(condition_id="other")]))
    with pytest.raises(ValueError, match="unique"):
        _verify(_artifact(comparisons=[_comparison(), _comparison()]))


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"analysis_complete": False}, "analysis_complete"),
        ({"delta_orientation": "reference_minus_condition"}, "delta_orientation"),
        ({"bootstrap_rounds": 99}, "bootstrap_rounds"),
        ({"bootstrap_rounds": True}, "bootstrap_rounds"),
        ({"bootstrap_seed": True}, "bootstrap_seed"),
        ({"bootstrap_confidence": 0.5}, "bootstrap_confidence"),
        ({"bootstrap_confidence": "nan"}, "finite"),
        ({"tie_tolerance": -1}, "tie_tolerance"),
    ],
)
def test_p51_rejects_invalid_analysis_settings(overrides: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _verify(_artifact(inference_overrides=overrides))


def test_p51_rejects_malformed_ci_and_count_types() -> None:
    with pytest.raises(ValueError, match="exactly two"):
        _verify(_artifact(comparisons=[_comparison(bootstrap_mean_delta_ci=["4"])]))
    with pytest.raises(ValueError, match="pair_count"):
        _verify(_artifact(comparisons=[_comparison(pair_count=True)]))


def test_p51_rejects_incompatible_or_drifted_p50() -> None:
    result = _artifact()
    binding, semantics, pairing, descriptives, delta_inventory = _inputs(result)
    with pytest.raises(ValueError, match="incompatible or unverified"):
        verify_ablation_raw_sample_pairwise_inference(
            replace(delta_inventory, delta_inventory_verified=False),
            descriptives,
            pairing,
            semantics,
            binding,
            result_artifact=result,
            raw_sample_artifacts=RAW,
        )
    with pytest.raises(ValueError, match="does not match"):
        verify_ablation_raw_sample_pairwise_inference(
            replace(delta_inventory, delta_inventory_sha256="44" * 32),
            descriptives,
            pairing,
            semantics,
            binding,
            result_artifact=result,
            raw_sample_artifacts=RAW,
        )


def test_p51_rejects_result_or_raw_sample_byte_drift() -> None:
    result = _artifact()
    binding, semantics, pairing, descriptives, delta_inventory = _inputs(result)
    with pytest.raises(ValueError):
        verify_ablation_raw_sample_pairwise_inference(
            delta_inventory,
            descriptives,
            pairing,
            semantics,
            binding,
            result_artifact=result + b" ",
            raw_sample_artifacts=RAW,
        )
    drifted = dict(RAW)
    drifted["a.jsonl"] = drifted["a.jsonl"] + b"\n"
    with pytest.raises(ValueError):
        verify_ablation_raw_sample_pairwise_inference(
            delta_inventory,
            descriptives,
            pairing,
            semantics,
            binding,
            result_artifact=result,
            raw_sample_artifacts=drifted,
        )
