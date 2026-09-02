from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_family import (
    AblationFamilyMemberResult,
    SearchQualityAblationFamilyReport,
)
from app.search_quality_ablation_result_outcome import (
    EVIDENCE_STATE,
    verify_ablation_result_outcome_consistency,
)
from app.search_quality_ablation_result_semantics import (
    RESULT_SCHEMA,
    AblationResultSemanticVerification,
)

ARTIFACT_SHA = "07" * 32
PROVENANCE_SHA = "b2" * 32
COMMIT = "a1" * 20
RUNTIME = "python-3.14-linux-x86_64"
KIND = "paired-ablation-family-result"
SEMANTIC_SHA = "d4" * 32


def _family(*, accepted: bool = False) -> SearchQualityAblationFamilyReport:
    members = (
        AblationFamilyMemberResult("no-beam", 0.01, 0.02, True, True),
        AblationFamilyMemberResult("no-cost-model", 0.04, 0.04, False, True),
    )
    return SearchQualityAblationFamilyReport(
        measurement_source_id="heldout-source",
        protocol="frozen-v1",
        machine_fingerprint="machine-a",
        reference_label="full-system",
        workload_count=8,
        candidate_count=24,
        top_k=3,
        family_size=2,
        family_wise_alpha=0.05,
        correction_method="holm_step_down_family_wise_error_control",
        members=members,
        all_effects_accepted=accepted,
        all_multiplicity_tests_accepted=True,
        acceptance_passed=accepted,
    )


def _document(family: SearchQualityAblationFamilyReport | None = None, **overrides: object) -> bytes:
    report = family or _family()
    value: dict[str, object] = {
        "schema": RESULT_SCHEMA,
        "artifact_verification_sha256": ARTIFACT_SHA,
        "execution_provenance_sha256": PROVENANCE_SHA,
        "implementation_commit_sha": COMMIT,
        "runtime_id": RUNTIME,
        "result_kind": KIND,
        "accepted": report.acceptance_passed,
        "family": {
            "measurement_source_id": report.measurement_source_id,
            "protocol": report.protocol,
            "machine_fingerprint": report.machine_fingerprint,
            "reference_label": report.reference_label,
            "family_size": report.family_size,
            "family_wise_alpha": report.family_wise_alpha,
            "correction_method": report.correction_method,
            "members": [member.as_dict() for member in report.members],
        },
        "automatic_control_allowed": False,
    }
    value.update(overrides)
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _semantics(raw: bytes) -> AblationResultSemanticVerification:
    return AblationResultSemanticVerification(
        result_binding_sha256="c3" * 32,
        result_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        artifact_verification_sha256=ARTIFACT_SHA,
        execution_provenance_sha256=PROVENANCE_SHA,
        implementation_commit_sha=COMMIT,
        runtime_id=RUNTIME,
        result_kind=KIND,
        schema=RESULT_SCHEMA,
        semantic_verification_sha256=SEMANTIC_SHA,
        semantic_consistency_verified=True,
    )


def test_outcome_consistency_verifies_negative_family_without_promoting_claims() -> None:
    family = _family()
    raw = _document(family)
    report = verify_ablation_result_outcome_consistency(_semantics(raw), family, result_artifact=raw)
    assert report.outcome_consistency_verified is True
    assert report.acceptance_passed is False
    assert report.member_count == 2
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    truth = report.as_dict()["truth_boundary"]
    assert "does not prove" in truth
    assert "benchmark/search superiority" in truth


def test_outcome_consistency_accepts_equivalent_member_order_but_preserves_byte_bound_identity() -> None:
    family = _family()
    first_raw = _document(family)
    first = verify_ablation_result_outcome_consistency(_semantics(first_raw), family, result_artifact=first_raw)

    document = json.loads(first_raw)
    members = list(reversed(document["family"]["members"]))
    members[0]["ablated_label"] = members[0]["ablated_label"].upper()
    members[1]["ablated_label"] = members[1]["ablated_label"].upper()
    document["family"]["members"] = members
    second_raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    second = verify_ablation_result_outcome_consistency(_semantics(second_raw), family, result_artifact=second_raw)
    assert second.outcome_consistency_verified is True
    assert first.acceptance_passed == second.acceptance_passed
    assert first.member_count == second.member_count
    assert first.outcome_verification_sha256 != second.outcome_verification_sha256


def test_outcome_consistency_rejects_false_acceptance_claim() -> None:
    family = _family()
    raw = _document(family, accepted=True)
    with pytest.raises(ValueError, match="accepted does not match"):
        verify_ablation_result_outcome_consistency(_semantics(raw), family, result_artifact=raw)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("measurement_source_id", "other-source"),
        ("protocol", "other-protocol"),
        ("machine_fingerprint", "other-machine"),
        ("reference_label", "other-reference"),
        ("correction_method", "other-method"),
    ],
)
def test_outcome_consistency_rejects_family_metadata_drift(field: str, value: object) -> None:
    family = _family()
    document = json.loads(_document(family))
    document["family"][field] = value
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match=f"family.{field} does not match"):
        verify_ablation_result_outcome_consistency(_semantics(raw), family, result_artifact=raw)


def test_outcome_consistency_rejects_family_size_alpha_and_member_coverage_drift() -> None:
    family = _family()
    for field, value, pattern in (
        ("family_size", 3, "family.family_size does not match"),
        ("family_wise_alpha", 0.01, "family.family_wise_alpha does not match"),
    ):
        document = json.loads(_document(family))
        document["family"][field] = value
        raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        with pytest.raises(ValueError, match=pattern):
            verify_ablation_result_outcome_consistency(_semantics(raw), family, result_artifact=raw)

    document = json.loads(_document(family))
    document["family"]["members"].pop()
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="cover every"):
        verify_ablation_result_outcome_consistency(_semantics(raw), family, result_artifact=raw)


def test_outcome_consistency_rejects_member_statistical_or_effect_drift() -> None:
    family = _family()
    for field, value in (
        ("raw_one_sided_p_value", 0.5),
        ("holm_adjusted_p_value", 0.5),
        ("effect_acceptance_passed", True),
        ("multiplicity_acceptance_passed", False),
    ):
        document = json.loads(_document(family))
        document["family"]["members"][1][field] = value
        raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        with pytest.raises(ValueError, match=f"{field} does not match"):
            verify_ablation_result_outcome_consistency(_semantics(raw), family, result_artifact=raw)


def test_outcome_consistency_rejects_duplicate_or_unknown_member_labels() -> None:
    family = _family()
    document = json.loads(_document(family))
    document["family"]["members"][1]["ablated_label"] = "NO-BEAM"
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="duplicate normalized"):
        verify_ablation_result_outcome_consistency(_semantics(raw), family, result_artifact=raw)

    document = json.loads(_document(family))
    document["family"]["members"][1]["ablated_label"] = "unknown"
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="unknown ablated_label"):
        verify_ablation_result_outcome_consistency(_semantics(raw), family, result_artifact=raw)


def test_outcome_consistency_rejects_unverified_incompatible_or_control_authorizing_inputs() -> None:
    family = _family()
    raw = _document(family)
    semantics = _semantics(raw)
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_outcome_consistency(replace(semantics, evidence_state="OTHER"), family, result_artifact=raw)
    with pytest.raises(ValueError, match="must be verified"):
        verify_ablation_result_outcome_consistency(
            replace(semantics, semantic_consistency_verified=False), family, result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_outcome_consistency(
            replace(semantics, automatic_control_allowed=True), family, result_artifact=raw
        )
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_outcome_consistency(
            semantics, replace(family, evidence_state="OTHER"), result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_outcome_consistency(
            semantics, replace(family, automatic_control_allowed=True), result_artifact=raw
        )


def test_outcome_consistency_rejects_byte_drift_invalid_booleans_and_inconsistent_family() -> None:
    family = _family()
    bound = _document(family)
    changed = _document(family, note="changed")
    with pytest.raises(ValueError, match="bytes do not match"):
        verify_ablation_result_outcome_consistency(_semantics(bound), family, result_artifact=changed)

    document = json.loads(bound)
    document["accepted"] = 0
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="accepted must be a boolean"):
        verify_ablation_result_outcome_consistency(_semantics(raw), family, result_artifact=raw)

    with pytest.raises(ValueError, match="family size is inconsistent"):
        verify_ablation_result_outcome_consistency(
            _semantics(bound), replace(family, family_size=3), result_artifact=bound
        )
