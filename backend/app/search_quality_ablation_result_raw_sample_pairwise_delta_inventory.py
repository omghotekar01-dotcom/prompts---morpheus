"""Deterministic paired-delta inventory binding for P49-verified MORPHEUS raw samples.

P50 preserves the exact condition-minus-reference delta distribution behind P49's aggregate
paired means. It binds canonical per-pair deltas to the byte-bound result so downstream research
checks can reproduce the supplied distribution without treating this gate as inferential evidence.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .search_quality_ablation_result_raw_sample_pairing import AblationRawSamplePairingConsistency
from .search_quality_ablation_result_raw_sample_pairwise_descriptives import (
    EVIDENCE_STATE as DESCRIPTIVES_EVIDENCE_STATE,
    AblationRawSamplePairwiseDescriptives,
    verify_ablation_raw_sample_pairwise_descriptives,
)
from .search_quality_ablation_result_raw_sample_semantics import AblationRawSampleSemanticConsistency
from .search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_PAIRWISE_DELTA_INVENTORY"
TRUTH_BOUNDARY = (
    "This gate proves only that exact P49-verified caller-supplied records produce the declared canonical "
    "per-pair condition-minus-reference delta inventory and content hashes. It does not establish measurement "
    "genuineness, independence, randomization, representativeness, statistical significance, confidence-interval "
    "coverage, effect-size validity, causal attribution, benchmark/search superiority, publication-grade evidence, "
    "novelty, patentability, production readiness, or automatic-control authorization."
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


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class AblationRawSamplePairwiseDeltaInventory:
    descriptives_sha256: str
    reference_condition_id: str
    comparison_count: int
    pair_count: int
    delta_record_count: int
    delta_inventory_sha256: str
    delta_inventory_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_ablation_raw_sample_pairwise_delta_inventory(
    descriptives: AblationRawSamplePairwiseDescriptives,
    pairing: AblationRawSamplePairingConsistency,
    semantics: AblationRawSampleSemanticConsistency,
    binding: AblationResultRawSampleBinding,
    *, result_artifact: bytes | str,
    raw_sample_artifacts: Mapping[str, bytes | str],
) -> AblationRawSamplePairwiseDeltaInventory:
    if descriptives.evidence_state != DESCRIPTIVES_EVIDENCE_STATE or not descriptives.descriptives_verified:
        raise ValueError("P49 descriptive evidence is incompatible or unverified")
    if descriptives.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    recomputed = verify_ablation_raw_sample_pairwise_descriptives(
        pairing, semantics, binding, result_artifact=result_artifact, raw_sample_artifacts=raw_sample_artifacts
    )
    if recomputed != descriptives:
        raise ValueError("supplied P49 descriptives do not match the exact result/raw-sample bytes")

    result_raw = _raw("result_artifact", result_artifact)
    try:
        document = json.loads(result_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(document, dict) or document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must be an object with automatic_control_allowed=false")
    raw_evidence = document.get("raw_sample_evidence")
    declaration = raw_evidence.get("pairwise_delta_inventory") if isinstance(raw_evidence, dict) else None
    if not isinstance(declaration, dict):
        raise ValueError("raw_sample_evidence.pairwise_delta_inventory must be an object")
    if declaration.get("inventory_complete") is not True:
        raise ValueError("pairwise_delta_inventory.inventory_complete must be true")
    declared_comparisons = declaration.get("comparisons")
    if not isinstance(declared_comparisons, list) or not declared_comparisons:
        raise ValueError("pairwise_delta_inventory.comparisons must be a non-empty list")

    reference = descriptives.reference_condition_id
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

    comparison_conditions = sorted(conditions - {reference})
    normalized_declared: dict[str, tuple[int, str]] = {}
    for item in declared_comparisons:
        if not isinstance(item, dict):
            raise ValueError("each pairwise delta inventory comparison must be an object")
        condition = _text("condition_id", item.get("condition_id"))
        if condition in normalized_declared:
            raise ValueError("pairwise delta inventory condition_id values must be unique")
        pair_count = item.get("pair_count")
        if isinstance(pair_count, bool) or not isinstance(pair_count, int) or pair_count <= 0:
            raise ValueError("pairwise delta inventory pair_count must be a positive integer")
        digest = _text("pair_delta_sha256", item.get("pair_delta_sha256")).lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("pair_delta_sha256 must be a 64-character hexadecimal SHA-256")
        normalized_declared[condition] = (pair_count, digest)
    if sorted(normalized_declared) != comparison_conditions:
        raise ValueError("declared pairwise delta inventory conditions do not match raw samples")

    canonical_all: list[dict[str, object]] = []
    for condition in comparison_conditions:
        rows: list[dict[str, object]] = []
        for (workload, repetition), values in sorted(pairs.items()):
            row = {
                "condition_id": condition,
                "workload_id": workload,
                "repetition_index": repetition,
                "delta": _canonical_decimal(values[condition] - values[reference]),
            }
            rows.append(row)
            canonical_all.append(row)
        observed = (len(rows), _sha(rows))
        if normalized_declared[condition] != observed:
            raise ValueError(f"declared pairwise delta inventory does not match raw samples for {condition!r}")

    payload = {
        "descriptives_sha256": descriptives.descriptives_sha256.lower(),
        "reference_condition_id": reference,
        "comparisons": [
            {"condition_id": condition, "pair_count": normalized_declared[condition][0], "pair_delta_sha256": normalized_declared[condition][1]}
            for condition in comparison_conditions
        ],
        "delta_records": canonical_all,
    }
    return AblationRawSamplePairwiseDeltaInventory(
        descriptives_sha256=descriptives.descriptives_sha256.lower(),
        reference_condition_id=reference,
        comparison_count=len(comparison_conditions),
        pair_count=descriptives.pair_count,
        delta_record_count=len(canonical_all),
        delta_inventory_sha256=_sha(payload),
        delta_inventory_verified=True,
    )
