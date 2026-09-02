from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_result_disclosure import AblationResultDisclosureVerification
from app.search_quality_ablation_result_validity import (
    EVIDENCE_STATE,
    verify_ablation_result_validity_consistency,
)
from app.search_quality_ablation_validity import AblationValidityThreatsReport, REQUIRED_CATEGORIES

PLAN_SHA = "aa" * 32
DISCLOSURE_SHA = "bb" * 32
THREATS_SHA = "cc" * 32
DISCLOSURE_VERIFICATION_SHA = "dd" * 32


def _validity() -> AblationValidityThreatsReport:
    return AblationValidityThreatsReport(
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256=PLAN_SHA,
        disclosure_sha256=DISCLOSURE_SHA,
        family_size=3,
        threat_count=4,
        covered_categories=tuple(sorted(REQUIRED_CATEGORIES)),
        category_coverage_complete=True,
        threats_sha256=THREATS_SHA,
        acceptance_passed=True,
    )


def _document(validity: AblationValidityThreatsReport | None = None, **overrides: object) -> bytes:
    report = validity or _validity()
    value: dict[str, object] = {
        "schema": "morpheus.ablation-result/v1",
        "validity": {
            "plan_id": report.plan_id,
            "plan_sha256": report.plan_sha256,
            "disclosure_sha256": report.disclosure_sha256,
            "family_size": report.family_size,
            "threat_count": report.threat_count,
            "covered_categories": list(report.covered_categories),
            "category_coverage_complete": report.category_coverage_complete,
            "threats_sha256": report.threats_sha256,
            "acceptance_passed": report.acceptance_passed,
        },
        "automatic_control_allowed": False,
    }
    value.update(overrides)
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _disclosure_verification(raw: bytes) -> AblationResultDisclosureVerification:
    return AblationResultDisclosureVerification(
        outcome_verification_sha256="ee" * 32,
        result_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256=PLAN_SHA,
        disclosure_sha256=DISCLOSURE_SHA,
        family_size=3,
        disclosed_count=3,
        accepted_count=2,
        not_accepted_count=1,
        disclosure_verification_sha256=DISCLOSURE_VERIFICATION_SHA,
        disclosure_consistency_verified=True,
    )


def test_result_validity_consistency_binds_required_category_coverage() -> None:
    validity = _validity()
    raw = _document(validity)
    report = verify_ablation_result_validity_consistency(
        _disclosure_verification(raw), validity, result_artifact=raw
    )
    assert report.validity_consistency_verified is True
    assert report.covered_categories == tuple(sorted(REQUIRED_CATEGORIES))
    assert report.threat_count == 4
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    truth = report.as_dict()["truth_boundary"]
    assert "listed threats are exhaustive" in truth
    assert "no benchmark/search superiority" in truth


def test_result_validity_identity_is_deterministic_for_identical_bound_evidence() -> None:
    validity = _validity()
    raw = _document(validity)
    bound = _disclosure_verification(raw)
    first = verify_ablation_result_validity_consistency(bound, validity, result_artifact=raw)
    second = verify_ablation_result_validity_consistency(bound, validity, result_artifact=raw)
    assert first.validity_verification_sha256 == second.validity_verification_sha256


def test_result_validity_accepts_normalized_category_spelling_but_byte_identity_remains_bound() -> None:
    validity = _validity()
    document = json.loads(_document(validity))
    document["validity"]["covered_categories"] = [
        "Statistical Conclusion Validity",
        "External-Validity",
        "INTERNAL_VALIDITY",
        "construct validity",
    ]
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    report = verify_ablation_result_validity_consistency(
        _disclosure_verification(raw), validity, result_artifact=raw
    )
    assert report.covered_categories == tuple(sorted(REQUIRED_CATEGORIES))
    assert report.result_artifact_sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("plan_id", "other-plan"),
        ("plan_sha256", "11" * 32),
        ("disclosure_sha256", "22" * 32),
        ("threats_sha256", "33" * 32),
        ("family_size", 4),
        ("threat_count", 5),
    ],
)
def test_result_validity_rejects_declared_identity_or_count_drift(field: str, value: object) -> None:
    validity = _validity()
    document = json.loads(_document(validity))
    document["validity"][field] = value
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match=f"validity.{field}"):
        verify_ablation_result_validity_consistency(
            _disclosure_verification(raw), validity, result_artifact=raw
        )


def test_result_validity_rejects_missing_duplicate_or_incomplete_categories() -> None:
    validity = _validity()
    for categories in (
        list(REQUIRED_CATEGORIES[:-1]),
        [*REQUIRED_CATEGORIES[:-1], REQUIRED_CATEGORIES[0]],
    ):
        document = json.loads(_document(validity))
        document["validity"]["covered_categories"] = categories
        raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        with pytest.raises(ValueError, match="covered_categories"):
            verify_ablation_result_validity_consistency(
                _disclosure_verification(raw), validity, result_artifact=raw
            )

    for field in ("category_coverage_complete", "acceptance_passed"):
        document = json.loads(_document(validity))
        document["validity"][field] = False
        raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        with pytest.raises(ValueError, match=field):
            verify_ablation_result_validity_consistency(
                _disclosure_verification(raw), validity, result_artifact=raw
            )


def test_result_validity_rejects_invalid_declared_types() -> None:
    validity = _validity()
    document = json.loads(_document(validity))
    document["validity"]["threat_count"] = True
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="non-negative integer"):
        verify_ablation_result_validity_consistency(
            _disclosure_verification(raw), validity, result_artifact=raw
        )

    document = json.loads(_document(validity))
    document["validity"]["covered_categories"] = "construct_validity"
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="must be an array"):
        verify_ablation_result_validity_consistency(
            _disclosure_verification(raw), validity, result_artifact=raw
        )


def test_result_validity_rejects_inconsistent_p34_binding_or_coverage() -> None:
    validity = _validity()
    raw = _document(validity)
    bound = _disclosure_verification(raw)
    with pytest.raises(ValueError, match="plan_id must match"):
        verify_ablation_result_validity_consistency(
            bound, replace(validity, plan_id="other"), result_artifact=raw
        )
    with pytest.raises(ValueError, match="family_size must match"):
        verify_ablation_result_validity_consistency(
            bound, replace(validity, family_size=4), result_artifact=raw
        )
    with pytest.raises(ValueError, match="threat_count"):
        verify_ablation_result_validity_consistency(
            bound, replace(validity, threat_count=3), result_artifact=raw
        )
    with pytest.raises(ValueError, match="covered_categories"):
        verify_ablation_result_validity_consistency(
            bound, replace(validity, covered_categories=("construct_validity",) * 4), result_artifact=raw
        )


def test_result_validity_rejects_unverified_or_control_authorizing_inputs() -> None:
    validity = _validity()
    raw = _document(validity)
    bound = _disclosure_verification(raw)
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_validity_consistency(
            replace(bound, evidence_state="OTHER"), validity, result_artifact=raw
        )
    with pytest.raises(ValueError, match="must be verified"):
        verify_ablation_result_validity_consistency(
            replace(bound, disclosure_consistency_verified=False), validity, result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_validity_consistency(
            replace(bound, automatic_control_allowed=True), validity, result_artifact=raw
        )
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_validity_consistency(
            bound, replace(validity, evidence_state="OTHER"), result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_validity_consistency(
            bound, replace(validity, automatic_control_allowed=True), result_artifact=raw
        )


def test_result_validity_rejects_byte_drift_and_control_promotion() -> None:
    validity = _validity()
    bound_raw = _document(validity)
    changed = _document(validity, note="changed")
    with pytest.raises(ValueError, match="bytes do not match"):
        verify_ablation_result_validity_consistency(
            _disclosure_verification(bound_raw), validity, result_artifact=changed
        )

    document = json.loads(bound_raw)
    document["automatic_control_allowed"] = True
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="explicitly set automatic_control_allowed to false"):
        verify_ablation_result_validity_consistency(
            _disclosure_verification(raw), validity, result_artifact=raw
        )
