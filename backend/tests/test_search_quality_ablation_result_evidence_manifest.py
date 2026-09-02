from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_evidence_manifest import AblationResearchEvidenceManifest
from app.search_quality_ablation_result_evidence_manifest import (
    EVIDENCE_STATE,
    verify_ablation_result_evidence_manifest_consistency,
)
from app.search_quality_ablation_result_validity import AblationResultValidityVerification

PLAN_SHA = "aa" * 32
DISCLOSURE_SHA = "bb" * 32
THREATS_SHA = "cc" * 32
MANIFEST_SHA = "dd" * 32
VALIDITY_VERIFICATION_SHA = "ee" * 32


def _manifest() -> AblationResearchEvidenceManifest:
    return AblationResearchEvidenceManifest(
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256=PLAN_SHA,
        disclosure_sha256=DISCLOSURE_SHA,
        threats_sha256=THREATS_SHA,
        family_size=3,
        measurement_source_id="source-v1",
        protocol="paired-fixed-workload-v1",
        machine_fingerprint="machine-v1",
        reference_label="full",
        workload_count=10,
        candidate_count=3,
        top_k=3,
        family_wise_alpha=0.05,
        correction_method="holm",
        family_acceptance_passed=False,
        disclosed_accepted_count=2,
        disclosed_not_accepted_count=1,
        evidence_manifest_sha256=MANIFEST_SHA,
        integrity_passed=True,
    )


def _document(manifest: AblationResearchEvidenceManifest | None = None, **overrides: object) -> bytes:
    report = manifest or _manifest()
    value: dict[str, object] = {
        "schema": "morpheus.ablation-result/v1",
        "evidence_manifest": {
            "plan_id": report.plan_id,
            "plan_sha256": report.plan_sha256,
            "disclosure_sha256": report.disclosure_sha256,
            "threats_sha256": report.threats_sha256,
            "family_size": report.family_size,
            "evidence_manifest_sha256": report.evidence_manifest_sha256,
            "integrity_passed": report.integrity_passed,
        },
        "automatic_control_allowed": False,
    }
    value.update(overrides)
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validity(raw: bytes) -> AblationResultValidityVerification:
    return AblationResultValidityVerification(
        disclosure_verification_sha256="11" * 32,
        result_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256=PLAN_SHA,
        disclosure_sha256=DISCLOSURE_SHA,
        family_size=3,
        threat_count=4,
        covered_categories=(
            "construct_validity",
            "external_validity",
            "internal_validity",
            "statistical_conclusion_validity",
        ),
        threats_sha256=THREATS_SHA,
        validity_verification_sha256=VALIDITY_VERIFICATION_SHA,
        validity_consistency_verified=True,
    )


def test_result_manifest_consistency_binds_p35_identity() -> None:
    manifest = _manifest()
    raw = _document(manifest)
    report = verify_ablation_result_evidence_manifest_consistency(
        _validity(raw), manifest, result_artifact=raw
    )
    assert report.evidence_manifest_consistency_verified is True
    assert report.evidence_manifest_sha256 == MANIFEST_SHA
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    truth = report.as_dict()["truth_boundary"]
    assert "preregistration preceded observation" in truth
    assert "no benchmark/search superiority" in truth


def test_result_manifest_identity_is_deterministic() -> None:
    manifest = _manifest()
    raw = _document(manifest)
    bound = _validity(raw)
    first = verify_ablation_result_evidence_manifest_consistency(bound, manifest, result_artifact=raw)
    second = verify_ablation_result_evidence_manifest_consistency(bound, manifest, result_artifact=raw)
    assert first.manifest_verification_sha256 == second.manifest_verification_sha256


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("plan_id", "other-plan"),
        ("plan_sha256", "12" * 32),
        ("disclosure_sha256", "23" * 32),
        ("threats_sha256", "34" * 32),
        ("family_size", 4),
        ("evidence_manifest_sha256", "45" * 32),
    ],
)
def test_result_manifest_rejects_declared_identity_or_count_drift(field: str, value: object) -> None:
    manifest = _manifest()
    document = json.loads(_document(manifest))
    document["evidence_manifest"][field] = value
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match=f"evidence_manifest.{field}"):
        verify_ablation_result_evidence_manifest_consistency(
            _validity(raw), manifest, result_artifact=raw
        )


def test_result_manifest_rejects_inconsistent_p35_binding() -> None:
    manifest = _manifest()
    raw = _document(manifest)
    bound = _validity(raw)
    for changed, pattern in (
        (replace(manifest, plan_id="other"), "plan_id must match"),
        (replace(manifest, plan_sha256="12" * 32), "plan_sha256 must match"),
        (replace(manifest, disclosure_sha256="23" * 32), "disclosure_sha256 must match"),
        (replace(manifest, threats_sha256="34" * 32), "threats_sha256 must match"),
        (replace(manifest, family_size=4), "family_size must match"),
    ):
        with pytest.raises(ValueError, match=pattern):
            verify_ablation_result_evidence_manifest_consistency(
                bound, changed, result_artifact=raw
            )


def test_result_manifest_rejects_unverified_or_control_authorizing_inputs() -> None:
    manifest = _manifest()
    raw = _document(manifest)
    bound = _validity(raw)
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_evidence_manifest_consistency(
            replace(bound, evidence_state="OTHER"), manifest, result_artifact=raw
        )
    with pytest.raises(ValueError, match="must be verified"):
        verify_ablation_result_evidence_manifest_consistency(
            replace(bound, validity_consistency_verified=False), manifest, result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_evidence_manifest_consistency(
            replace(bound, automatic_control_allowed=True), manifest, result_artifact=raw
        )
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_evidence_manifest_consistency(
            bound, replace(manifest, evidence_state="OTHER"), result_artifact=raw
        )
    with pytest.raises(ValueError, match="integrity_passed"):
        verify_ablation_result_evidence_manifest_consistency(
            bound, replace(manifest, integrity_passed=False), result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_evidence_manifest_consistency(
            bound, replace(manifest, automatic_control_allowed=True), result_artifact=raw
        )


def test_result_manifest_rejects_malformed_manifest_declaration() -> None:
    manifest = _manifest()
    document = json.loads(_document(manifest))
    document["evidence_manifest"] = "not-an-object"
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="must be an object"):
        verify_ablation_result_evidence_manifest_consistency(
            _validity(raw), manifest, result_artifact=raw
        )

    document = json.loads(_document(manifest))
    document["evidence_manifest"]["family_size"] = True
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="positive integer"):
        verify_ablation_result_evidence_manifest_consistency(
            _validity(raw), manifest, result_artifact=raw
        )


def test_result_manifest_rejects_byte_drift_and_control_promotion() -> None:
    manifest = _manifest()
    bound_raw = _document(manifest)
    changed = _document(manifest, note="changed")
    with pytest.raises(ValueError, match="bytes do not match"):
        verify_ablation_result_evidence_manifest_consistency(
            _validity(bound_raw), manifest, result_artifact=changed
        )

    document = json.loads(bound_raw)
    document["automatic_control_allowed"] = True
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="explicitly set automatic_control_allowed to false"):
        verify_ablation_result_evidence_manifest_consistency(
            _validity(raw), manifest, result_artifact=raw
        )
