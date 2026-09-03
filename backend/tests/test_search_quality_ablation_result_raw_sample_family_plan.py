from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

import app.search_quality_ablation_result_raw_sample_family_plan as p53
from app.search_quality_ablation_preregistration import AblationAnalysisPlan
from app.search_quality_ablation_result_evidence_manifest import AblationResultEvidenceManifestVerification
from app.search_quality_ablation_result_raw_sample_pairwise_family_correction import (
    AblationRawSamplePairwiseFamilyCorrectionConsistency,
)


def _plan(**overrides: object) -> AblationAnalysisPlan:
    values: dict[str, object] = {
        "plan_id": "plan-1",
        "measurement_source_id": "native-benchmark",
        "protocol": "ablation-v1",
        "machine_fingerprint": "m",
        "reference_label": "reference",
        "workload_count": 1,
        "candidate_count": 3,
        "top_k": 1,
        "expected_ablated_labels": ("a", "b"),
        "minimum_required_mean_regret_ratio_improvement": 0.01,
        "maximum_allowed_one_sided_p_value": 0.05,
        "family_wise_alpha": 0.05,
    }
    values.update(overrides)
    return AblationAnalysisPlan(**values)  # type: ignore[arg-type]


def _artifact(
    *,
    comparisons: object = None,
    alpha: object = "0.05",
    automatic_control_allowed: object = False,
) -> bytes:
    return json.dumps(
        {
            "raw_sample_evidence": {
                "pairwise_family_correction": {
                    "family_wise_alpha": alpha,
                    "comparisons": comparisons
                    if comparisons is not None
                    else [{"condition_id": "b"}, {"condition_id": "A"}],
                }
            },
            "automatic_control_allowed": automatic_control_allowed,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _family(**overrides: object) -> AblationRawSamplePairwiseFamilyCorrectionConsistency:
    values: dict[str, object] = {
        "inference_sha256": "11" * 32,
        "reference_condition_id": "REFERENCE",
        "family_size": 2,
        "family_wise_alpha": "0.0500",
        "correction_method": "HOLM_BONFERRONI_STEP_DOWN",
        "rejected_count": 0,
        "family_correction_sha256": "22" * 32,
        "family_correction_verified": True,
    }
    values.update(overrides)
    return AblationRawSamplePairwiseFamilyCorrectionConsistency(**values)  # type: ignore[arg-type]


def _manifest(result: bytes, plan: AblationAnalysisPlan, **overrides: object) -> AblationResultEvidenceManifestVerification:
    values: dict[str, object] = {
        "validity_verification_sha256": "33" * 32,
        "result_artifact_sha256": hashlib.sha256(result).hexdigest(),
        "plan_id": plan.plan_id,
        "plan_sha256": plan.sha256(),
        "disclosure_sha256": "44" * 32,
        "threats_sha256": "55" * 32,
        "family_size": 2,
        "evidence_manifest_sha256": "66" * 32,
        "manifest_verification_sha256": "77" * 32,
        "evidence_manifest_consistency_verified": True,
    }
    values.update(overrides)
    return AblationResultEvidenceManifestVerification(**values)  # type: ignore[arg-type]


def _verify(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: bytes | None = None,
    plan: AblationAnalysisPlan | None = None,
    family: AblationRawSamplePairwiseFamilyCorrectionConsistency | None = None,
    manifest: AblationResultEvidenceManifestVerification | None = None,
):
    result = _artifact() if result is None else result
    plan = _plan() if plan is None else plan
    family = _family() if family is None else family
    manifest = _manifest(result, plan) if manifest is None else manifest
    monkeypatch.setattr(p53, "verify_ablation_raw_sample_pairwise_family_correction", lambda *args, **kwargs: family)
    placeholder = SimpleNamespace()
    return p53.verify_ablation_raw_sample_family_plan_consistency(
        family,
        placeholder,
        placeholder,
        placeholder,
        placeholder,
        placeholder,
        placeholder,
        manifest,
        plan,
        result_artifact=result,
        raw_sample_artifacts={"raw.jsonl": b"sample"},
    )


def test_p53_binds_p52_family_to_p32_plan_deterministically(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _verify(monkeypatch)
    second = _verify(monkeypatch)
    equivalent = _verify(
        monkeypatch,
        result=_artifact(comparisons=[{"condition_id": "a"}, {"condition_id": "B"}], alpha=0.05000),
    )
    assert first.family_plan_consistency_verified is True
    assert first.automatic_control_allowed is False
    assert first.normalized_family_members == ("a", "b")
    assert first.reference_condition_id == "reference"
    assert first.family_wise_alpha == "0.05"
    assert first.family_plan_binding_sha256 == second.family_plan_binding_sha256
    assert equivalent.normalized_family_members == first.normalized_family_members
    assert equivalent.family_wise_alpha == first.family_wise_alpha
    assert equivalent.family_plan_binding_sha256 != first.family_plan_binding_sha256


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evidence_state", "WRONG", "incompatible evidence_state"),
        ("family_correction_verified", False, "must be verified"),
        ("automatic_control_allowed", True, "cannot authorize automatic control"),
    ],
)
def test_p53_rejects_incompatible_p52_evidence(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, family=replace(_family(), **{field: value}))


def test_p53_rejects_p52_recomputation_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _artifact()
    plan = _plan()
    family = _family()
    manifest = _manifest(result, plan)
    monkeypatch.setattr(
        p53,
        "verify_ablation_raw_sample_pairwise_family_correction",
        lambda *args, **kwargs: replace(family, family_correction_sha256="88" * 32),
    )
    placeholder = SimpleNamespace()
    with pytest.raises(ValueError, match="does not match the exact result/raw-sample bytes"):
        p53.verify_ablation_raw_sample_family_plan_consistency(
            family,
            placeholder,
            placeholder,
            placeholder,
            placeholder,
            placeholder,
            placeholder,
            manifest,
            plan,
            result_artifact=result,
            raw_sample_artifacts={"raw.jsonl": b"sample"},
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evidence_state", "WRONG", "incompatible evidence_state"),
        ("evidence_manifest_consistency_verified", False, "must be verified"),
        ("automatic_control_allowed", True, "cannot authorize automatic control"),
    ],
)
def test_p53_rejects_incompatible_p43_evidence(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object, message: str
) -> None:
    result = _artifact()
    plan = _plan()
    manifest = replace(_manifest(result, plan), **{field: value})
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, result=result, plan=plan, manifest=manifest)


def test_p53_requires_p43_and_p52_to_bind_same_result_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _artifact()
    plan = _plan()
    manifest = replace(_manifest(result, plan), result_artifact_sha256="99" * 32)
    with pytest.raises(ValueError, match="same result artifact bytes"):
        _verify(monkeypatch, result=result, plan=plan, manifest=manifest)


@pytest.mark.parametrize(
    ("manifest_overrides", "message"),
    [
        ({"plan_id": "other-plan"}, "plan_id"),
        ({"plan_sha256": "99" * 32}, "plan content"),
        ({"family_size": 3}, "family_size"),
    ],
)
def test_p53_rejects_p43_plan_identity_or_family_drift(
    monkeypatch: pytest.MonkeyPatch, manifest_overrides: dict[str, object], message: str
) -> None:
    result = _artifact()
    plan = _plan()
    manifest = replace(_manifest(result, plan), **manifest_overrides)
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, result=result, plan=plan, manifest=manifest)


def test_p53_rejects_family_membership_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _artifact(comparisons=[{"condition_id": "a"}, {"condition_id": "c"}])
    with pytest.raises(ValueError, match="family membership"):
        _verify(monkeypatch, result=result)


def test_p53_rejects_duplicate_normalized_family_members(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(expected_ablated_labels=("a", "A"))
    result = _artifact(comparisons=[{"condition_id": "a"}, {"condition_id": "A"}])
    manifest = _manifest(result, plan)
    with pytest.raises(ValueError, match="distinct after normalization"):
        _verify(monkeypatch, result=result, plan=plan, manifest=manifest)


def test_p53_rejects_reference_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="reference condition"):
        _verify(monkeypatch, family=_family(reference_condition_id="other"))


@pytest.mark.parametrize("alpha", ["0.04", 0.06])
def test_p53_rejects_family_wise_alpha_drift(monkeypatch: pytest.MonkeyPatch, alpha: object) -> None:
    with pytest.raises(ValueError, match="family-wise alpha"):
        _verify(monkeypatch, result=_artifact(alpha=alpha))


def test_p53_rejects_plan_alpha_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(family_wise_alpha=0.01)
    result = _artifact()
    manifest = _manifest(result, plan)
    with pytest.raises(ValueError, match="family-wise alpha"):
        _verify(monkeypatch, result=result, plan=plan, manifest=manifest)


@pytest.mark.parametrize(
    "result",
    [
        b"not-json",
        json.dumps({"raw_sample_evidence": {}, "automatic_control_allowed": False}).encode(),
        json.dumps({"raw_sample_evidence": {"pairwise_family_correction": {}}, "automatic_control_allowed": True}).encode(),
    ],
)
def test_p53_rejects_malformed_or_control_authorizing_result(
    monkeypatch: pytest.MonkeyPatch, result: bytes
) -> None:
    plan = _plan()
    manifest = _manifest(result, plan)
    with pytest.raises(ValueError):
        _verify(monkeypatch, result=result, plan=plan, manifest=manifest)
