"""Deterministic paired inferential consistency for P50-bound MORPHEUS raw samples.

P51 recomputes protocol-required paired summaries from the exact P50-bound sample bytes: win/tie/loss
counts, exact two-sided sign test, paired effect size, and deterministic bootstrap confidence interval.
It verifies reporting consistency only; it does not upgrade caller-supplied measurements into causal,
benchmark-superiority, publication-grade, or production evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .research_suite import PairedObservation, analyze_paired_measurements
from .search_quality_ablation_result_raw_sample_pairing import AblationRawSamplePairingConsistency
from .search_quality_ablation_result_raw_sample_pairwise_delta_inventory import (
    EVIDENCE_STATE as DELTA_INVENTORY_EVIDENCE_STATE,
    AblationRawSamplePairwiseDeltaInventory,
    verify_ablation_raw_sample_pairwise_delta_inventory,
)
from .search_quality_ablation_result_raw_sample_pairwise_descriptives import AblationRawSamplePairwiseDescriptives
from .search_quality_ablation_result_raw_sample_semantics import AblationRawSampleSemanticConsistency
from .search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_PAIRWISE_INFERENCE"
TRUTH_BOUNDARY = (
    "This gate proves only that exact P50-verified caller-supplied paired records reproduce the declared "
    "win/tie/loss counts, exact two-sided sign-test p-value, paired effect size, and deterministic bootstrap "
    "confidence interval under the declared analysis settings. It does not establish measurement genuineness, "
    "independence, randomization, representativeness, model assumptions, multiplicity control, causal attribution, "
    "benchmark/search superiority, publication-grade evidence, novelty, patentability, production readiness, or "
    "automatic-control authorization."
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


def _strict_int(name: str, value: object, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{name} must be a finite numeric value")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite numeric value") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _canonical_number(value: float | None) -> str | None:
    if value is None:
        return None
    try:
        decimal = Decimal(str(value))
    except InvalidOperation as exc:  # defensive; research_suite already guarantees finite values
        raise ValueError("analysis produced a non-decimal value") from exc
    if decimal == 0:
        return "0"
    text = format(decimal.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _declared_number(name: str, value: object, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    return _canonical_number(_finite_float(name, value))


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class AblationRawSamplePairwiseInferenceConsistency:
    delta_inventory_sha256: str
    reference_condition_id: str
    comparison_count: int
    pair_count: int
    bootstrap_rounds: int
    bootstrap_seed: int
    bootstrap_confidence: str
    inference_sha256: str
    inference_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_ablation_raw_sample_pairwise_inference(
    delta_inventory: AblationRawSamplePairwiseDeltaInventory,
    descriptives: AblationRawSamplePairwiseDescriptives,
    pairing: AblationRawSamplePairingConsistency,
    semantics: AblationRawSampleSemanticConsistency,
    binding: AblationResultRawSampleBinding,
    *,
    result_artifact: bytes | str,
    raw_sample_artifacts: Mapping[str, bytes | str],
) -> AblationRawSamplePairwiseInferenceConsistency:
    if delta_inventory.evidence_state != DELTA_INVENTORY_EVIDENCE_STATE or not delta_inventory.delta_inventory_verified:
        raise ValueError("P50 delta-inventory evidence is incompatible or unverified")
    if delta_inventory.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")

    recomputed = verify_ablation_raw_sample_pairwise_delta_inventory(
        descriptives,
        pairing,
        semantics,
        binding,
        result_artifact=result_artifact,
        raw_sample_artifacts=raw_sample_artifacts,
    )
    if recomputed != delta_inventory:
        raise ValueError("supplied P50 delta inventory does not match the exact result/raw-sample bytes")

    result_raw = _raw("result_artifact", result_artifact)
    try:
        document = json.loads(result_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(document, dict) or document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must be an object with automatic_control_allowed=false")
    raw_evidence = document.get("raw_sample_evidence")
    declaration = raw_evidence.get("pairwise_inference") if isinstance(raw_evidence, dict) else None
    if not isinstance(declaration, dict):
        raise ValueError("raw_sample_evidence.pairwise_inference must be an object")
    if declaration.get("analysis_complete") is not True:
        raise ValueError("pairwise_inference.analysis_complete must be true")
    if declaration.get("delta_orientation") != "condition_minus_reference":
        raise ValueError("pairwise_inference.delta_orientation must be condition_minus_reference")

    bootstrap_rounds = _strict_int("bootstrap_rounds", declaration.get("bootstrap_rounds"), minimum=100)
    if bootstrap_rounds > 100_000:
        raise ValueError("bootstrap_rounds must be <= 100000")
    bootstrap_seed = _strict_int("bootstrap_seed", declaration.get("bootstrap_seed"))
    confidence = _finite_float("bootstrap_confidence", declaration.get("bootstrap_confidence"))
    if not 0.5 < confidence < 1.0:
        raise ValueError("bootstrap_confidence must be between 0.5 and 1")
    tie_tolerance = _finite_float("tie_tolerance", declaration.get("tie_tolerance", 1e-12))
    if tie_tolerance < 0:
        raise ValueError("tie_tolerance must be non-negative")

    declared = declaration.get("comparisons")
    if not isinstance(declared, list) or not declared:
        raise ValueError("pairwise_inference.comparisons must be a non-empty list")
    declared_by_condition: dict[str, dict[str, object]] = {}
    for item in declared:
        if not isinstance(item, dict):
            raise ValueError("each pairwise inference comparison must be an object")
        condition = _text("condition_id", item.get("condition_id"))
        if condition in declared_by_condition:
            raise ValueError("pairwise inference condition_id values must be unique")
        declared_by_condition[condition] = item

    pairs: dict[tuple[str, int], dict[str, float]] = {}
    conditions: set[str] = set()
    for artifact_id, content in raw_sample_artifacts.items():
        text = _raw(_text("artifact_id", artifact_id), content).decode("utf-8")
        for line in (line for line in text.splitlines() if line.strip()):
            record = json.loads(line)
            condition = _text("condition_id", record.get("condition_id"))
            workload = _text("workload_id", record.get("workload_id"))
            repetition = _strict_int("repetition_index", record.get("repetition_index"), minimum=0)
            pairs.setdefault((workload, repetition), {})[condition] = _finite_float("value", record.get("value"))
            conditions.add(condition)

    reference = delta_inventory.reference_condition_id
    comparison_conditions = sorted(conditions - {reference})
    if sorted(declared_by_condition) != comparison_conditions:
        raise ValueError("declared pairwise inference conditions do not match raw samples")

    canonical_results: list[dict[str, object]] = []
    for condition in comparison_conditions:
        observations = [
            PairedObservation(
                label=f"{workload}:{repetition}",
                baseline=values[reference],
                treatment=values[condition],
            )
            for (workload, repetition), values in sorted(pairs.items())
        ]
        analysis = analyze_paired_measurements(
            metric=semantics.metric,
            observations=observations,
            lower_is_better=False,
            bootstrap_rounds=bootstrap_rounds,
            bootstrap_seed=bootstrap_seed,
            confidence=confidence,
            tie_tolerance=tie_tolerance,
        )
        item = declared_by_condition[condition]
        expected = {
            "condition_id": condition,
            "pair_count": analysis.sample_count,
            "wins": analysis.wins,
            "ties": analysis.ties,
            "losses": analysis.losses,
            "mean_delta": _canonical_number(analysis.mean_improvement),
            "median_delta": _canonical_number(analysis.median_improvement),
            "paired_effect_dz": _canonical_number(analysis.paired_effect_dz),
            "exact_sign_test_p_two_sided": _canonical_number(analysis.exact_sign_test_p_two_sided),
            "bootstrap_mean_delta_ci": [
                _canonical_number(analysis.bootstrap_mean_improvement_ci[0]),
                _canonical_number(analysis.bootstrap_mean_improvement_ci[1]),
            ],
        }
        observed = {
            "condition_id": condition,
            "pair_count": _strict_int("pair_count", item.get("pair_count"), minimum=1),
            "wins": _strict_int("wins", item.get("wins"), minimum=0),
            "ties": _strict_int("ties", item.get("ties"), minimum=0),
            "losses": _strict_int("losses", item.get("losses"), minimum=0),
            "mean_delta": _declared_number("mean_delta", item.get("mean_delta")),
            "median_delta": _declared_number("median_delta", item.get("median_delta")),
            "paired_effect_dz": _declared_number("paired_effect_dz", item.get("paired_effect_dz"), allow_none=True),
            "exact_sign_test_p_two_sided": _declared_number(
                "exact_sign_test_p_two_sided", item.get("exact_sign_test_p_two_sided"), allow_none=True
            ),
            "bootstrap_mean_delta_ci": None,
        }
        ci = item.get("bootstrap_mean_delta_ci")
        if not isinstance(ci, list) or len(ci) != 2:
            raise ValueError("bootstrap_mean_delta_ci must contain exactly two values")
        observed["bootstrap_mean_delta_ci"] = [
            _declared_number("bootstrap_mean_delta_ci[0]", ci[0]),
            _declared_number("bootstrap_mean_delta_ci[1]", ci[1]),
        ]
        if observed != expected:
            raise ValueError(f"declared pairwise inference does not match raw samples for {condition!r}")
        canonical_results.append(expected)

    payload = {
        "delta_inventory_sha256": delta_inventory.delta_inventory_sha256.lower(),
        "reference_condition_id": reference,
        "delta_orientation": "condition_minus_reference",
        "bootstrap_rounds": bootstrap_rounds,
        "bootstrap_seed": bootstrap_seed,
        "bootstrap_confidence": _canonical_number(confidence),
        "tie_tolerance": _canonical_number(tie_tolerance),
        "comparisons": canonical_results,
    }
    return AblationRawSamplePairwiseInferenceConsistency(
        delta_inventory_sha256=delta_inventory.delta_inventory_sha256.lower(),
        reference_condition_id=reference,
        comparison_count=len(comparison_conditions),
        pair_count=delta_inventory.pair_count,
        bootstrap_rounds=bootstrap_rounds,
        bootstrap_seed=bootstrap_seed,
        bootstrap_confidence=_canonical_number(confidence) or "0",
        inference_sha256=_sha(payload),
        inference_verified=True,
    )
