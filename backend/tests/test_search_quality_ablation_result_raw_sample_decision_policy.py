from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

import app.search_quality_ablation_result_raw_sample_decision_policy as subject
from app.search_quality_ablation_preregistration import AblationAnalysisPlan


def _plan(**changes: object) -> AblationAnalysisPlan:
    values: dict[str, object] = {
        "plan_id": "plan-1", "measurement_source_id": "bench", "protocol": "protocol-v1",
        "machine_fingerprint": "machine-a", "reference_label": "reference", "workload_count": 2,
        "candidate_count": 8, "top_k": 3, "expected_ablated_labels": ("no-model", "no-pruning"),
        "minimum_required_mean_regret_ratio_improvement": 0.1,
        "maximum_allowed_one_sided_p_value": 0.05, "family_wise_alpha": 0.05,
    }
    values.update(changes)
    return AblationAnalysisPlan(**values)  # type: ignore[arg-type]


def _result(*, minimum: object = 0.1, maximum_p: object = 0.05, automatic_control: object = False) -> bytes:
    return json.dumps({
        "automatic_control_allowed": automatic_control,
        "raw_sample_evidence": {"semantics": {
            "minimum_required_mean_regret_ratio_improvement": minimum,
            "maximum_allowed_one_sided_p_value": maximum_p,
        }},
    }, sort_keys=True, separators=(",", ":")).encode()


def _policy(plan: AblationAnalysisPlan, result: bytes, **changes: object):
    values: dict[str, object] = {
        "family_plan_context_sha256": "1" * 64,
        "result_artifact_sha256": hashlib.sha256(result).hexdigest(),
        "plan_id": plan.plan_id, "plan_sha256": plan.sha256(),
        "candidate_count": plan.candidate_count, "top_k": plan.top_k,
        "search_policy_binding_sha256": "2" * 64,
        "search_policy_consistency_verified": True,
        "evidence_state": subject.SEARCH_POLICY_EVIDENCE_STATE,
        "automatic_control_allowed": False,
    }
    values.update(changes)
    return subject.AblationRawSampleSearchPolicyConsistency(**values)  # type: ignore[arg-type]


def _verify(monkeypatch: pytest.MonkeyPatch, *, plan=None, result=None, policy=None):
    plan = plan or _plan()
    result = result or _result(
        minimum=plan.minimum_required_mean_regret_ratio_improvement,
        maximum_p=plan.maximum_allowed_one_sided_p_value,
    )
    policy = policy or _policy(plan, result)
    monkeypatch.setattr(subject, "verify_ablation_raw_sample_search_policy_consistency", lambda *a, **k: policy)
    return subject.verify_ablation_raw_sample_decision_policy_consistency(
        policy,
        None, None, None, None, None, None, None, None, None, None,  # type: ignore[arg-type]
        plan,
        result_artifact=result,
        raw_sample_artifacts={"samples.jsonl": b"{}"},
    )


def test_p56_binds_decision_policy_deterministically(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _verify(monkeypatch)
    second = _verify(monkeypatch)
    assert first == second
    assert first.minimum_required_mean_regret_ratio_improvement == 0.1
    assert first.maximum_allowed_one_sided_p_value == 0.05
    assert first.decision_policy_consistency_verified is True
    assert first.automatic_control_allowed is False
    assert len(first.decision_policy_binding_sha256) == 64
    assert first.as_dict()["truth_boundary"] == subject.TRUTH_BOUNDARY


@pytest.mark.parametrize(("minimum", "maximum_p", "message"), [
    (0.2, 0.05, "minimum_required_mean_regret_ratio_improvement does not match"),
    (0.1, 0.1, "maximum_allowed_one_sided_p_value does not match"),
    (-0.1, 0.05, "must be non-negative"),
    (0.1, 0.0, "must be in"),
    (0.1, 1.1, "must be in"),
    (True, 0.05, "must be a finite number"),
    (0.1, True, "must be a finite number"),
    (None, 0.05, "must be a finite number"),
])
def test_p56_rejects_invalid_or_drifted_thresholds(
    monkeypatch: pytest.MonkeyPatch, minimum: object, maximum_p: object, message: str
) -> None:
    plan = _plan()
    result = _result(minimum=minimum, maximum_p=maximum_p)
    policy = _policy(plan, result)
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, plan=plan, result=result, policy=policy)


@pytest.mark.parametrize(("field", "value", "message"), [
    ("evidence_state", "wrong", "incompatible evidence_state"),
    ("search_policy_consistency_verified", False, "must be verified"),
    ("automatic_control_allowed", True, "cannot authorize automatic control"),
])
def test_p56_rejects_invalid_p55_state(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object, message: str
) -> None:
    plan = _plan(); result = _result(); policy = replace(_policy(plan, result), **{field: value})
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, plan=plan, result=result, policy=policy)


def test_p56_rejects_p55_recomputation_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(); result = _result(); policy = _policy(plan, result)
    monkeypatch.setattr(subject, "verify_ablation_raw_sample_search_policy_consistency", lambda *a, **k: replace(policy, top_k=2))
    with pytest.raises(ValueError, match="does not match the exact result/raw-sample bytes"):
        subject.verify_ablation_raw_sample_decision_policy_consistency(
            policy, None, None, None, None, None, None, None, None, None, None, plan,  # type: ignore[arg-type]
            result_artifact=result, raw_sample_artifacts={"samples.jsonl": b"{}"},
        )


def test_p56_rejects_result_byte_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(); result = _result(); policy = _policy(plan, result)
    monkeypatch.setattr(subject, "verify_ablation_raw_sample_search_policy_consistency", lambda *a, **k: policy)
    with pytest.raises(ValueError, match="does not bind the supplied result artifact bytes"):
        subject.verify_ablation_raw_sample_decision_policy_consistency(
            policy, None, None, None, None, None, None, None, None, None, None, plan,  # type: ignore[arg-type]
            result_artifact=result + b"\n", raw_sample_artifacts={"samples.jsonl": b"{}"},
        )


def test_p56_rejects_result_automatic_control(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(); result = _result(automatic_control=True); policy = _policy(plan, result)
    with pytest.raises(ValueError, match="automatic_control_allowed=false"):
        _verify(monkeypatch, plan=plan, result=result, policy=policy)
