from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

import app.search_quality_ablation_result_raw_sample_plan_coverage as subject
from app.search_quality_ablation_preregistration import AblationAnalysisPlan


def _plan(**changes: object) -> AblationAnalysisPlan:
    values: dict[str, object] = {
        "plan_id": "plan-1", "measurement_source_id": "bench", "protocol": "protocol-v1",
        "machine_fingerprint": "machine-a", "reference_label": "Reference", "workload_count": 2,
        "candidate_count": 8, "top_k": 3, "expected_ablated_labels": ("No-Model", "No-Pruning"),
        "minimum_required_mean_regret_ratio_improvement": 0.1,
        "maximum_allowed_one_sided_p_value": 0.05, "family_wise_alpha": 0.05,
    }
    values.update(changes)
    return AblationAnalysisPlan(**values)  # type: ignore[arg-type]


def _evidence(plan: AblationAnalysisPlan, result: bytes):
    result_sha = hashlib.sha256(result).hexdigest()
    family = subject.AblationRawSampleFamilyPlanConsistency(
        family_correction_sha256="a" * 64, result_artifact_sha256=result_sha,
        plan_id=plan.plan_id, plan_sha256=plan.sha256(), reference_condition_id="reference",
        family_size=2, family_wise_alpha="0.05",
        normalized_family_members=("no-model", "no-pruning"), family_plan_binding_sha256="b" * 64,
        family_plan_consistency_verified=True,
    )
    context = subject.AblationRawSampleFamilyPlanContextConsistency(
        family_plan_binding_sha256=family.family_plan_binding_sha256,
        semantic_verification_sha256="c" * 64, result_artifact_sha256=result_sha,
        plan_id=plan.plan_id, plan_sha256=plan.sha256(), measurement_source_id="bench",
        protocol="protocol-v1", machine_fingerprint="machine-a", workload_count=2,
        normalized_condition_ids=("no-model", "no-pruning", "reference"),
        family_plan_context_sha256="d" * 64, family_plan_context_consistency_verified=True,
    )
    search = subject.AblationRawSampleSearchPolicyConsistency(
        family_plan_context_sha256=context.family_plan_context_sha256,
        result_artifact_sha256=result_sha, plan_id=plan.plan_id, plan_sha256=plan.sha256(),
        candidate_count=8, top_k=3, search_policy_binding_sha256="e" * 64,
        search_policy_consistency_verified=True,
    )
    decision = subject.AblationRawSampleDecisionPolicyConsistency(
        search_policy_binding_sha256=search.search_policy_binding_sha256,
        result_artifact_sha256=result_sha, plan_id=plan.plan_id, plan_sha256=plan.sha256(),
        minimum_required_mean_regret_ratio_improvement=0.1,
        maximum_allowed_one_sided_p_value=0.05, decision_policy_binding_sha256="f" * 64,
        decision_policy_consistency_verified=True,
    )
    return decision, search, context, family


def _verify(monkeypatch: pytest.MonkeyPatch, *, plan=None, result=None, changes=None):
    plan = plan or _plan()
    result = result or b'{"automatic_control_allowed":false}'
    decision, search, context, family = _evidence(plan, result)
    changes = changes or {}
    decision = replace(decision, **changes.get("decision", {}))
    search = replace(search, **changes.get("search", {}))
    context = replace(context, **changes.get("context", {}))
    family = replace(family, **changes.get("family", {}))
    monkeypatch.setattr(
        subject, "verify_ablation_raw_sample_decision_policy_consistency",
        lambda *a, **k: decision,
    )
    return subject.verify_ablation_raw_sample_plan_coverage(
        decision, search, context, family,
        None, None, None, None, None, None, None, None,
        plan,
        result_artifact=result, raw_sample_artifacts={"samples.jsonl": b"{}"},
    )


def test_p57_seals_complete_p32_plan_coverage_deterministically(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _verify(monkeypatch)
    second = _verify(monkeypatch)
    assert first == second
    assert first.covered_plan_fields == subject.COVERED_PLAN_FIELDS
    assert first.covered_field_count == 12
    assert set(first.covered_plan_fields) == set(_plan().canonical_payload())
    assert first.complete_plan_coverage_verified is True
    assert first.automatic_control_allowed is False
    assert len(first.plan_coverage_sha256) == 64
    assert first.as_dict()["truth_boundary"] == subject.TRUTH_BOUNDARY


@pytest.mark.parametrize(("scope", "field", "value", "message"), [
    ("decision", "evidence_state", "wrong", "incompatible evidence_state"),
    ("decision", "decision_policy_consistency_verified", False, "must be verified"),
    ("decision", "automatic_control_allowed", True, "cannot authorize automatic control"),
    ("context", "measurement_source_id", "other", "covered measurement_source_id"),
    ("context", "protocol", "other", "covered protocol"),
    ("context", "machine_fingerprint", "other", "covered machine_fingerprint"),
    ("context", "workload_count", 3, "covered workload_count"),
    ("search", "candidate_count", 9, "candidate_count/top_k"),
    ("search", "top_k", 2, "candidate_count/top_k"),
    ("family", "reference_condition_id", "other", "covered reference_label"),
    ("family", "normalized_family_members", ("no-model", "other"), "expected_ablated_labels"),
    ("family", "family_wise_alpha", "0.1", "family_wise_alpha"),
    ("decision", "minimum_required_mean_regret_ratio_improvement", 0.2, "minimum effect threshold"),
    ("decision", "maximum_allowed_one_sided_p_value", 0.1, "one-sided p-value threshold"),
])
def test_p57_rejects_unbound_or_drifted_plan_values(
    monkeypatch: pytest.MonkeyPatch, scope: str, field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, changes={scope: {field: value}})


@pytest.mark.parametrize(("scope", "field", "value", "message"), [
    ("decision", "search_policy_binding_sha256", "0" * 64, "does not bind the supplied P55"),
    ("search", "family_plan_context_sha256", "0" * 64, "does not bind the supplied P54"),
    ("context", "family_plan_binding_sha256", "0" * 64, "does not bind the supplied P53"),
    ("family", "result_artifact_sha256", "0" * 64, "do not bind one exact result artifact"),
])
def test_p57_rejects_broken_chain_identity(
    monkeypatch: pytest.MonkeyPatch, scope: str, field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, changes={scope: {field: value}})


def test_p57_rejects_p56_recomputation_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(); result = b'{"automatic_control_allowed":false}'
    decision, search, context, family = _evidence(plan, result)
    monkeypatch.setattr(
        subject, "verify_ablation_raw_sample_decision_policy_consistency",
        lambda *a, **k: replace(decision, maximum_allowed_one_sided_p_value=0.1),
    )
    with pytest.raises(ValueError, match="does not match the exact result/raw-sample bytes"):
        subject.verify_ablation_raw_sample_plan_coverage(
            decision, search, context, family,
            None, None, None, None, None, None, None, None, plan,
            result_artifact=result, raw_sample_artifacts={"samples.jsonl": b"{}"},
        )


def test_p57_fails_closed_when_p32_canonical_schema_grows(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    original = subject.AblationAnalysisPlan.canonical_payload

    def expanded_payload(self):
        return {**original(self), "future_policy_field": "must-be-explicitly-bound"}

    monkeypatch.setattr(subject.AblationAnalysisPlan, "canonical_payload", expanded_payload)
    with pytest.raises(ValueError, match="field coverage is incomplete or stale"):
        _verify(monkeypatch, plan=plan)


def test_p57_rejects_plan_identity_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(); result = b'{"automatic_control_allowed":false}'
    decision, search, context, family = _evidence(plan, result)
    decision = replace(decision, plan_id="other")
    monkeypatch.setattr(subject, "verify_ablation_raw_sample_decision_policy_consistency", lambda *a, **k: decision)
    with pytest.raises(ValueError, match="plan_id does not match"):
        subject.verify_ablation_raw_sample_plan_coverage(
            decision, search, context, family,
            None, None, None, None, None, None, None, None, plan,
            result_artifact=result, raw_sample_artifacts={"samples.jsonl": b"{}"},
        )
