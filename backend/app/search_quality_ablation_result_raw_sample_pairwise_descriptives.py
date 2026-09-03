"""Deterministic paired descriptive-delta binding for P48-complete MORPHEUS raw samples.

P49 recomputes arithmetic condition-minus-reference deltas from the exact P46/P47/P48-bound
records and verifies a byte-bound result declaration. It is descriptive only: no significance,
effect-size validity, causality, superiority, or production claim is inferred.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .search_quality_ablation_result_raw_sample_pairing import (
    EVIDENCE_STATE as PAIRING_EVIDENCE_STATE,
    AblationRawSamplePairingConsistency,
    verify_ablation_raw_sample_pairing,
)
from .search_quality_ablation_result_raw_sample_semantics import AblationRawSampleSemanticConsistency
from .search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_PAIRWISE_DESCRIPTIVES"
TRUTH_BOUNDARY = (
    "This gate proves only that exact P48-complete caller-supplied records produce the declared arithmetic "
    "condition-minus-reference paired means. It does not establish measurement genuineness, independence, "
    "randomization, representativeness, statistical significance, effect-size validity, causal attribution, "
    "benchmark/search superiority, publication-grade evidence, novelty, patentability, production readiness, "
    "or automatic-control authorization."
)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _raw(name: str, value: object) -> bytes:
    if isinstance(value, str):
        value = value.encode()
    if not isinstance(value, bytes) or not value:
        raise ValueError(f"{name} must be non-empty bytes or str")
    return value


def _decimal(name: str, value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{name} must be a finite decimal-compatible value")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a finite decimal-compatible value") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _canonical_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


@dataclass(frozen=True)
class AblationRawSamplePairwiseDescriptives:
    pairing_verification_sha256: str
    reference_condition_id: str
    comparison_count: int
    pair_count: int
    descriptives_sha256: str
    descriptives_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_ablation_raw_sample_pairwise_descriptives(
    pairing: AblationRawSamplePairingConsistency,
    semantics: AblationRawSampleSemanticConsistency,
    binding: AblationResultRawSampleBinding,
    *, result_artifact: bytes | str,
    raw_sample_artifacts: Mapping[str, bytes | str],
) -> AblationRawSamplePairwiseDescriptives:
    if pairing.evidence_state != PAIRING_EVIDENCE_STATE or not pairing.pairing_verified:
        raise ValueError("P48 pairing evidence is incompatible or unverified")
    if pairing.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    recomputed = verify_ablation_raw_sample_pairing(
        semantics, binding, result_artifact=result_artifact, raw_sample_artifacts=raw_sample_artifacts
    )
    if recomputed != pairing:
        raise ValueError("supplied P48 pairing does not match the exact result/raw-sample bytes")

    result_raw = _raw("result_artifact", result_artifact)
    try:
        document = json.loads(result_raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(document, dict) or document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must be an object with automatic_control_allowed=false")
    evidence = document.get("raw_sample_evidence")
    declaration = evidence.get("pairwise_descriptives") if isinstance(evidence, dict) else None
    if not isinstance(declaration, dict):
        raise ValueError("raw_sample_evidence.pairwise_descriptives must be an object")
    reference = _text("reference_condition_id", declaration.get("reference_condition_id"))
    declared = declaration.get("comparisons")
    if not isinstance(declared, list) or not declared:
        raise ValueError("pairwise_descriptives.comparisons must be a non-empty list")

    pairs: dict[tuple[str, int], dict[str, Decimal]] = {}
    conditions: set[str] = set()
    for artifact_id, content in raw_sample_artifacts.items():
        text = _raw(_text("artifact_id", artifact_id), content).decode("utf-8")
        for line in (line for line in text.splitlines() if line.strip()):
            record = json.loads(line)
            condition = _text("condition_id", record.get("condition_id"))
            workload = _text("workload_id", record.get("workload_id"))
            repetition = record.get("repetition_index")
            if isinstance(repetition, bool) or not isinstance(repetition, int) or repetition < 0:
                raise ValueError("repetition_index must be a non-negative integer")
            pairs.setdefault((workload, repetition), {})[condition] = _decimal("value", record.get("value"))
            conditions.add(condition)
    if reference not in conditions:
        raise ValueError("reference_condition_id is absent from raw samples")

    expected_conditions = sorted(conditions - {reference})
    if len(declared) != len(expected_conditions):
        raise ValueError("declared comparison count does not match non-reference conditions")
    normalized_declared: dict[str, tuple[int, str]] = {}
    for item in declared:
        if not isinstance(item, dict):
            raise ValueError("each pairwise comparison must be an object")
        condition = _text("condition_id", item.get("condition_id"))
        if condition in normalized_declared:
            raise ValueError("pairwise comparison condition_id values must be unique")
        pair_count = item.get("pair_count")
        if isinstance(pair_count, bool) or not isinstance(pair_count, int) or pair_count <= 0:
            raise ValueError("pair_count must be a positive integer")
        normalized_declared[condition] = (pair_count, _canonical_decimal(_decimal("mean_delta", item.get("mean_delta"))))
    if sorted(normalized_declared) != expected_conditions:
        raise ValueError("declared pairwise comparison conditions do not match raw samples")

    canonical: list[dict[str, object]] = []
    for condition in expected_conditions:
        deltas = [values[condition] - values[reference] for _, values in sorted(pairs.items())]
        mean = sum(deltas, Decimal(0)) / Decimal(len(deltas))
        observed = (len(deltas), _canonical_decimal(mean))
        if normalized_declared[condition] != observed:
            raise ValueError(f"declared pairwise descriptive does not match raw samples for {condition!r}")
        canonical.append({"condition_id": condition, "pair_count": observed[0], "mean_delta": observed[1]})

    payload = {
        "pairing_verification_sha256": pairing.pairing_verification_sha256.lower(),
        "reference_condition_id": reference,
        "comparisons": canonical,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return AblationRawSamplePairwiseDescriptives(
        pairing_verification_sha256=pairing.pairing_verification_sha256.lower(),
        reference_condition_id=reference,
        comparison_count=len(canonical),
        pair_count=pairing.complete_pair_count,
        descriptives_sha256=digest,
        descriptives_verified=True,
    )
