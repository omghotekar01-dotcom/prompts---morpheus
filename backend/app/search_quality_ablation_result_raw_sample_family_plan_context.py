"""Bind P53 family-plan evidence to the P47 raw-sample measurement context.

P53 proves that the raw-sample comparison family, reference, size, and family-wise alpha match the
P32 plan already bound into the result chain. It intentionally does not prove that the raw samples'
measurement context or complete condition/workload coverage matches that same plan. P54 closes only
that seam by re-verifying P53 and P47 against the exact supplied bytes, then binding source, protocol,
machine, workload cardinality, and condition coverage to the P32 plan.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

from .search_quality_ablation_preregistration import AblationAnalysisPlan
from .search_quality_ablation_result_evidence_manifest import AblationResultEvidenceManifestVerification
from .search_quality_ablation_result_raw_sample_family_plan import (
    EVIDENCE_STATE as FAMILY_PLAN_EVIDENCE_STATE,
    AblationRawSampleFamilyPlanConsistency,
    verify_ablation_raw_sample_family_plan_consistency,
)
from .search_quality_ablation_result_raw_sample_pairing import AblationRawSamplePairingConsistency
from .search_quality_ablation_result_raw_sample_pairwise_delta_inventory import AblationRawSamplePairwiseDeltaInventory
from .search_quality_ablation_result_raw_sample_pairwise_descriptives import AblationRawSamplePairwiseDescriptives
from .search_quality_ablation_result_raw_sample_pairwise_family_correction import (
    AblationRawSamplePairwiseFamilyCorrectionConsistency,
)
from .search_quality_ablation_result_raw_sample_pairwise_inference import AblationRawSamplePairwiseInferenceConsistency
from .search_quality_ablation_result_raw_sample_semantics import (
    EVIDENCE_STATE as SEMANTICS_EVIDENCE_STATE,
    AblationRawSampleSemanticConsistency,
    verify_ablation_raw_sample_semantics,
)
from .search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_FAMILY_PLAN_CONTEXT_CONSISTENCY"
TRUTH_BOUNDARY = (
    "This gate proves only that the exact P53/P47-verified caller-supplied raw-sample bytes use the measurement "
    "source, protocol, machine fingerprint, workload cardinality, and complete reference-plus-ablation condition "
    "coverage declared by the same P32 plan already bound into the result chain. It does not prove that those "
    "identifiers describe the environment truthfully, that measurements are genuine, independent, randomized, "
    "representative, unbiased, or complete outside the supplied bytes, that the plan predates observation, or that "
    "undisclosed analyses do not exist. Passing establishes no causal validity, benchmark/search superiority, "
    "publication-grade evidence, novelty, patentability, production readiness, or automatic-control authorization."
)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _label(name: str, value: object) -> str:
    return _text(name, value).casefold()


def _raw(name: str, value: object) -> bytes:
    if isinstance(value, str):
        value = value.encode("utf-8")
    if not isinstance(value, bytes) or not value:
        raise ValueError(f"{name} must be non-empty bytes or str")
    return value


def _hex(name: str, value: object) -> str:
    normalized = _text(name, value).casefold()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{name} must be a 64-character hexadecimal digest")
    return normalized


def _sha(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AblationRawSampleFamilyPlanContextConsistency:
    family_plan_binding_sha256: str
    semantic_verification_sha256: str
    result_artifact_sha256: str
    plan_id: str
    plan_sha256: str
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    workload_count: int
    normalized_condition_ids: tuple[str, ...]
    family_plan_context_sha256: str
    family_plan_context_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            **self.__dict__,
            "normalized_condition_ids": list(self.normalized_condition_ids),
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_raw_sample_family_plan_context_consistency(
    family_plan: AblationRawSampleFamilyPlanConsistency,
    family_correction: AblationRawSamplePairwiseFamilyCorrectionConsistency,
    inference: AblationRawSamplePairwiseInferenceConsistency,
    delta_inventory: AblationRawSamplePairwiseDeltaInventory,
    descriptives: AblationRawSamplePairwiseDescriptives,
    pairing: AblationRawSamplePairingConsistency,
    semantics: AblationRawSampleSemanticConsistency,
    binding: AblationResultRawSampleBinding,
    manifest_verification: AblationResultEvidenceManifestVerification,
    plan: AblationAnalysisPlan,
    *,
    result_artifact: bytes | str,
    raw_sample_artifacts: Mapping[str, bytes | str],
) -> AblationRawSampleFamilyPlanContextConsistency:
    """Require P47 raw-sample context/coverage to match the P32 plan bound by P53."""

    if family_plan.evidence_state != FAMILY_PLAN_EVIDENCE_STATE:
        raise ValueError("P53 family-plan evidence has an incompatible evidence_state")
    if not family_plan.family_plan_consistency_verified:
        raise ValueError("P53 family-plan consistency must be verified")
    if family_plan.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")

    recomputed_family_plan = verify_ablation_raw_sample_family_plan_consistency(
        family_correction,
        inference,
        delta_inventory,
        descriptives,
        pairing,
        semantics,
        binding,
        manifest_verification,
        plan,
        result_artifact=result_artifact,
        raw_sample_artifacts=raw_sample_artifacts,
    )
    if recomputed_family_plan != family_plan:
        raise ValueError("supplied P53 family-plan evidence does not match the exact result/raw-sample bytes")

    if semantics.evidence_state != SEMANTICS_EVIDENCE_STATE:
        raise ValueError("P47 semantic evidence has an incompatible evidence_state")
    if not semantics.semantics_verified:
        raise ValueError("P47 raw-sample semantics must be verified")
    if semantics.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    recomputed_semantics = verify_ablation_raw_sample_semantics(
        binding,
        result_artifact=result_artifact,
        raw_sample_artifacts=raw_sample_artifacts,
    )
    if recomputed_semantics != semantics:
        raise ValueError("supplied P47 semantic evidence does not match the exact result/raw-sample bytes")

    result_raw = _raw("result_artifact", result_artifact)
    actual_result_sha = hashlib.sha256(result_raw).hexdigest()
    if actual_result_sha != _hex("P53 result_artifact_sha256", family_plan.result_artifact_sha256):
        raise ValueError("P53 family-plan evidence does not bind the supplied result artifact bytes")
    if _text("P53 plan_id", family_plan.plan_id) != _text("plan.plan_id", plan.plan_id):
        raise ValueError("P53 plan_id does not match the supplied P32 plan")
    if _hex("P53 plan_sha256", family_plan.plan_sha256) != plan.sha256().casefold():
        raise ValueError("P53 plan content does not match the supplied P32 plan")

    try:
        document = json.loads(result_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(document, dict) or document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must be an object with automatic_control_allowed=false")
    raw_evidence = document.get("raw_sample_evidence")
    if not isinstance(raw_evidence, dict):
        raise ValueError("raw_sample_evidence must be an object")
    declaration = raw_evidence.get("semantics")
    if not isinstance(declaration, dict):
        raise ValueError("raw_sample_evidence.semantics must be an object")

    source = _text("raw-sample measurement_source", declaration.get("measurement_source"))
    protocol = _text("raw-sample protocol_id", declaration.get("protocol_id"))
    machine = _text("raw-sample machine_fingerprint", declaration.get("machine_fingerprint"))
    if source != _text("plan.measurement_source_id", plan.measurement_source_id):
        raise ValueError("raw-sample measurement source does not match the P32 plan")
    if protocol != _text("plan.protocol", plan.protocol):
        raise ValueError("raw-sample protocol does not match the P32 plan")
    if machine != _text("plan.machine_fingerprint", plan.machine_fingerprint):
        raise ValueError("raw-sample machine fingerprint does not match the P32 plan")

    declared_conditions = declaration.get("condition_ids")
    if not isinstance(declared_conditions, list) or not declared_conditions:
        raise ValueError("raw-sample condition_ids must be a non-empty list")
    observed_conditions_list = [_label("raw-sample condition_id", item) for item in declared_conditions]
    if len(set(observed_conditions_list)) != len(observed_conditions_list):
        raise ValueError("raw-sample condition_ids must be distinct after normalization")
    observed_conditions = tuple(sorted(observed_conditions_list))
    expected_conditions = tuple(
        sorted(
            [_label("plan.reference_label", plan.reference_label)]
            + [_label("plan.expected_ablated_label", item) for item in plan.expected_ablated_labels]
        )
    )
    if len(set(expected_conditions)) != len(expected_conditions):
        raise ValueError("P32 reference and ablation labels must be distinct after normalization")
    if observed_conditions != expected_conditions:
        raise ValueError("raw-sample condition coverage does not match the complete P32 plan")

    workloads: set[str] = set()
    if not isinstance(raw_sample_artifacts, Mapping) or not raw_sample_artifacts:
        raise ValueError("raw_sample_artifacts must be a non-empty mapping")
    for artifact_id, content in raw_sample_artifacts.items():
        raw = _raw(f"raw sample artifact {artifact_id!r}", content)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"raw sample artifact {artifact_id!r} must be UTF-8 JSONL") from exc
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"raw sample artifact {artifact_id!r} contains invalid JSONL") from exc
            if not isinstance(record, dict):
                raise ValueError(f"raw sample artifact {artifact_id!r} record must be an object")
            workloads.add(_text("raw-sample workload_id", record.get("workload_id")))
    if len(workloads) != plan.workload_count:
        raise ValueError("raw-sample workload cardinality does not match the P32 plan")

    payload = {
        "family_plan_binding_sha256": _hex(
            "P53 family_plan_binding_sha256", family_plan.family_plan_binding_sha256
        ),
        "semantic_verification_sha256": _hex(
            "P47 semantic_verification_sha256", semantics.semantic_verification_sha256
        ),
        "result_artifact_sha256": actual_result_sha,
        "plan_id": _text("plan.plan_id", plan.plan_id),
        "plan_sha256": plan.sha256().casefold(),
        "measurement_source_id": source,
        "protocol": protocol,
        "machine_fingerprint": machine,
        "workload_count": len(workloads),
        "normalized_condition_ids": list(observed_conditions),
    }
    return AblationRawSampleFamilyPlanContextConsistency(
        family_plan_binding_sha256=payload["family_plan_binding_sha256"],
        semantic_verification_sha256=payload["semantic_verification_sha256"],
        result_artifact_sha256=actual_result_sha,
        plan_id=payload["plan_id"],
        plan_sha256=payload["plan_sha256"],
        measurement_source_id=source,
        protocol=protocol,
        machine_fingerprint=machine,
        workload_count=len(workloads),
        normalized_condition_ids=observed_conditions,
        family_plan_context_sha256=_sha(payload),
        family_plan_context_consistency_verified=True,
    )
