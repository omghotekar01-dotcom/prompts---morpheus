from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from decimal import Decimal

import pytest

from app.multiple_comparisons import holm_bonferroni
from app.research_suite import PairedObservation, analyze_paired_measurements
from app.search_quality_ablation_result_raw_sample_pairing import PAIRING_KEYS, verify_ablation_raw_sample_pairing
from app.search_quality_ablation_result_raw_sample_pairwise_delta_inventory import verify_ablation_raw_sample_pairwise_delta_inventory
from app.search_quality_ablation_result_raw_sample_pairwise_descriptives import verify_ablation_raw_sample_pairwise_descriptives
from app.search_quality_ablation_result_raw_sample_pairwise_family_correction import (
    EVIDENCE_STATE,
    verify_ablation_raw_sample_pairwise_family_correction,
)
from app.search_quality_ablation_result_raw_sample_pairwise_inference import verify_ablation_raw_sample_pairwise_inference
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
    "a.jsonl": _jsonl(
        _record("s1", "reference", 0, 100),
        _record("s2", "a", 0, 108),
        _record("s3", "b", 0, 102),
    ),
    "b.jsonl": _jsonl(
        _record("s4", "reference", 1, 110),
        _record("s5", "a", 1, 114),
        _record("s6", "b", 1, 108),
    ),
}
VALUES = {"reference": [100.0, 110.0], "a": [108.0, 114.0], "b": [102.0, 108.0]}


def _canonical(value: float) -> str:
    decimal = Decimal(str(value))
    if decimal == 0:
        return "0"
    text = format(decimal.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _delta_rows(condition: str) -> list[dict[str, object]]:
    return [
        {"condition_id": condition, "workload_id": "w", "repetition_index": rep, "delta": _canonical(VALUES[condition][rep] - VALUES["reference"][rep])}
        for rep in range(2)
    ]


def _inference_item(condition: str) -> dict[str, object]:
    analysis = analyze_paired_measurements(
        metric="latency_ns",
        observations=[
            PairedObservation(label=f"w:{rep}", baseline=VALUES["reference"][rep], treatment=VALUES[condition][rep])
            for rep in range(2)
        ],
        lower_is_better=False,
        bootstrap_rounds=1000,
        bootstrap_seed=1337,
        confidence=0.95,
        tie_tolerance=1e-12,
    )
    return {
        "condition_id": condition,
        "pair_count": analysis.sample_count,
        "wins": analysis.wins,
        "ties": analysis.ties,
        "losses": analysis.losses,
        "mean_delta": _canonical(analysis.mean_improvement),
        "median_delta": _canonical(analysis.median_improvement),
        "paired_effect_dz": None if analysis.paired_effect_dz is None else _canonical(analysis.paired_effect_dz),
        "exact_sign_test_p_two_sided": None if analysis.exact_sign_test_p_two_sided is None else _canonical(analysis.exact_sign_test_p_two_sided),
        "bootstrap_mean_delta_ci": [_canonical(analysis.bootstrap_mean_improvement_ci[0]), _canonical(analysis.bootstrap_mean_improvement_ci[1])],
    }


def _family_items(alpha: float = 0.05) -> list[dict[str, object]]:
    p_values = {condition: float(_inference_item(condition)["exact_sign_test_p_two_sided"]) for condition in ("a", "b")}
    correction = holm_bonferroni(p_values, alpha=alpha)
    return [
        {
            "condition_id": item.label,
            "raw_p": _canonical(item.raw_p),
            "adjusted_p": _canonical(item.adjusted_p),
            "rejected": item.rejected,
            "rank": item.rank,
            "threshold": _canonical(item.threshold),
        }
        for item in correction.hypotheses
    ]


def _artifact(
    *,
    family_overrides: dict[str, object] | None = None,
    family_comparisons: object = None,
    inference_comparisons: object = None,
) -> bytes:
    inventory = [{"artifact_id": key, "sha256": hashlib.sha256(value).hexdigest()} for key, value in sorted(RAW.items())]
    family: dict[str, object] = {
        "correction_complete": True,
        "method": "HOLM_BONFERRONI_STEP_DOWN",
        "family_wise_alpha": "0.05",
        "family_size": 2,
        "comparisons": family_comparisons if family_comparisons is not None else _family_items(),
    }
    if family_overrides:
        family.update(family_overrides)
    inference = {
        "analysis_complete": True,
        "delta_orientation": "condition_minus_reference",
        "bootstrap_rounds": 1000,
        "bootstrap_seed": 1337,
        "bootstrap_confidence": "0.95",
        "tie_tolerance": "0.000000000001",
        "comparisons": inference_comparisons if inference_comparisons is not None else [_inference_item("a"), _inference_item("b")],
    }
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
                    "record_count": 6,
                    "condition_ids": ["reference", "a", "b"],
                },
                "pairing": {"pairing_keys": list(PAIRING_KEYS), "complete_pair_count": 2},
                "pairwise_descriptives": {
                    "reference_condition_id": "reference",
                    "comparisons": [
                        {"condition_id": "a", "pair_count": 2, "mean_delta": "6"},
                        {"condition_id": "b", "pair_count": 2, "mean_delta": "0"},
                    ],
                },
                "pairwise_delta_inventory": {
                    "inventory_complete": True,
                    "comparisons": [
                        {"condition_id": condition, "pair_count": 2, "pair_delta_sha256": _sha(_delta_rows(condition))}
                        for condition in ("a", "b")
                    ],
                },
                "pairwise_inference": inference,
                "pairwise_family_correction": family,
            },
            "automatic_control_allowed": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _inputs(result: bytes):
    inventory = [{"artifact_id": key, "sha256": hashlib.sha256(value).hexdigest()} for key, value in sorted(RAW.items())]
    binding = AblationResultRawSampleBinding(
        result_artifact_verification_sha256="11" * 32,
        result_artifact_sha256=hashlib.sha256(result).hexdigest(),
        raw_sample_inventory_sha256=_sha(inventory),
        raw_sample_artifact_count=2,
        raw_sample_binding_sha256="22" * 32,
        raw_sample_bytes_bound=True,
    )
    semantics = verify_ablation_raw_sample_semantics(binding, result_artifact=result, raw_sample_artifacts=RAW)
    pairing = verify_ablation_raw_sample_pairing(semantics, binding, result_artifact=result, raw_sample_artifacts=RAW)
    descriptives = verify_ablation_raw_sample_pairwise_descriptives(pairing, semantics, binding, result_artifact=result, raw_sample_artifacts=RAW)
    delta_inventory = verify_ablation_raw_sample_pairwise_delta_inventory(descriptives, pairing, semantics, binding, result_artifact=result, raw_sample_artifacts=RAW)
    inference = verify_ablation_raw_sample_pairwise_inference(delta_inventory, descriptives, pairing, semantics, binding, result_artifact=result, raw_sample_artifacts=RAW)
    return binding, semantics, pairing, descriptives, delta_inventory, inference


def _verify(result: bytes):
    binding, semantics, pairing, descriptives, delta_inventory, inference = _inputs(result)
    return verify_ablation_raw_sample_pairwise_family_correction(
        inference,
        delta_inventory,
        descriptives,
        pairing,
        semantics,
        binding,
        result_artifact=result,
        raw_sample_artifacts=RAW,
    )


def test_p52_verifies_complete_holm_family_deterministically() -> None:
    first = _verify(_artifact())
    reversed_items = list(reversed(_family_items()))
    second = _verify(_artifact(family_overrides={"family_wise_alpha": 0.0500}, family_comparisons=reversed_items))
    assert first.family_size == 2
    assert first.family_wise_alpha == "0.05"
    assert first.correction_method == "HOLM_BONFERRONI_STEP_DOWN"
    assert first.rejected_count == 0
    assert first.evidence_state == EVIDENCE_STATE and first.family_correction_verified
    assert not first.automatic_control_allowed
    assert first.family_correction_sha256 == second.family_correction_sha256


@pytest.mark.parametrize(
    "field,value",
    [
        ("raw_p", "0.25"),
        ("adjusted_p", "0.5"),
        ("rejected", True),
        ("rank", 2),
        ("threshold", "0.01"),
    ],
)
def test_p52_rejects_correction_drift(field: str, value: object) -> None:
    items = _family_items()
    items[0] = {**items[0], field: value}
    with pytest.raises(ValueError, match="does not match P51 p-values"):
        _verify(_artifact(family_comparisons=items))


def test_p52_rejects_family_membership_size_and_duplicates() -> None:
    items = _family_items()
    with pytest.raises(ValueError, match="family_size"):
        _verify(_artifact(family_overrides={"family_size": 3}))
    with pytest.raises(ValueError, match="complete family"):
        _verify(_artifact(family_comparisons=items[:1]))
    duplicate = [items[0], {**items[1], "condition_id": items[0]["condition_id"]}]
    with pytest.raises(ValueError, match="unique"):
        _verify(_artifact(family_comparisons=duplicate))


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"correction_complete": False}, "correction_complete"),
        ({"method": "BONFERRONI"}, "method"),
        ({"family_wise_alpha": 0}, "family_wise_alpha"),
        ({"family_wise_alpha": True}, "family_wise_alpha"),
        ({"family_size": True}, "family_size"),
    ],
)
def test_p52_rejects_invalid_family_declarations(overrides: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _verify(_artifact(family_overrides=overrides))


def test_p52_rejects_incompatible_or_drifted_p51() -> None:
    result = _artifact()
    binding, semantics, pairing, descriptives, delta_inventory, inference = _inputs(result)
    with pytest.raises(ValueError, match="incompatible or unverified"):
        verify_ablation_raw_sample_pairwise_family_correction(
            replace(inference, inference_verified=False), delta_inventory, descriptives, pairing, semantics, binding,
            result_artifact=result, raw_sample_artifacts=RAW,
        )
    with pytest.raises(ValueError, match="does not match"):
        verify_ablation_raw_sample_pairwise_family_correction(
            replace(inference, inference_sha256="44" * 32), delta_inventory, descriptives, pairing, semantics, binding,
            result_artifact=result, raw_sample_artifacts=RAW,
        )


def test_p52_rejects_result_or_raw_sample_byte_drift() -> None:
    result = _artifact()
    binding, semantics, pairing, descriptives, delta_inventory, inference = _inputs(result)
    with pytest.raises(ValueError):
        verify_ablation_raw_sample_pairwise_family_correction(
            inference, delta_inventory, descriptives, pairing, semantics, binding,
            result_artifact=result + b" ", raw_sample_artifacts=RAW,
        )
    drifted = dict(RAW)
    drifted["a.jsonl"] = drifted["a.jsonl"] + b"\n"
    with pytest.raises(ValueError):
        verify_ablation_raw_sample_pairwise_family_correction(
            inference, delta_inventory, descriptives, pairing, semantics, binding,
            result_artifact=result, raw_sample_artifacts=drifted,
        )
