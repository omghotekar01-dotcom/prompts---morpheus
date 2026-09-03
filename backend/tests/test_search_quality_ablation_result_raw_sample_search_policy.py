from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

import app.search_quality_ablation_result_raw_sample_search_policy as subject
from app.search_quality_ablation_preregistration import AblationAnalysisPlan
from app.search_quality_ablation_result_raw_sample_family_plan_context import (
    EVIDENCE_STATE as P54_EVIDENCE_STATE,
    AblationRawSampleFamilyPlanContextConsistency,
)


def _plan(**changes: object) -> AblationAnalysisPlan:
    values: dict[str, object] = {
        "plan_id": "plan-1",
        "measurement_source_id": "bench",
        "protocol": "protocol-v1",
        "machine_fingerprint": "machine-a",
        "reference_label": "reference",
        "workload_count": 2,
        "candidate_count": 8,
        "top_k": 3,
        "expected_ablated_labels": ("no-model", "no-pruning"),
        "minimum_required_mean_regret_ratio_improvement": 0.0,
        "maximum_allowed_one_sided_p_value": 0.05,
        "family_wise_alpha": 0.05,
    }
    values.update(changes)
    return AblationAnalysisPlan(**values)  # type: ignore[arg-type]


def _result(*, candidate_count: object = 8, top_k: object = 3, automatic_control: object = False) -> bytes:
    return json.dumps(
        {
            "automatic_control_allowed": automatic_control,
            "raw_sample_evidence": {
                "semantics": {
                    "schema": "morpheus.ablation-raw-sample/v1",
                    "measurement_source": "bench",
                    "protocol_id": "protocol-v1",
                    "machine_fingerprint": "machine-a",
                    "metric": "mean_regret_ratio",
                    "record_count": 6,
                    "condition_ids": ["reference", "no-model", "no-pruning"],
                    "candidate_count": candidate_count,
                    "top_k": top_k,
                }
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _context(plan: AblationAnalysisPlan, result: bytes, **changes: object) -> AblationRawSampleFamilyPlanContextConsistency:
    values: dict[str, object] = {
        "family_plan_binding_sha256": "1" * 64,
        "semantic_verification_sha256": "2" * 64,
        "result_artifact_sha256": hashlib.sha256(result).hexdigest(),
        "plan_id": plan.plan_id,
        "plan_sha256": plan.sha256(),
        "measurement_source_id": plan.measurement_source_id,
        "protocol": plan.protocol,
        "machine_fingerprint": plan.machine_fingerprint,
        "workload_count": plan.workload_count,
        "normalized_condition_ids": ("no-model", "no-pruning", "reference"),
        "family_plan_context_sha256": "3" * 64,
        "family_plan_context_consistency_verified": True,
        "evidence_state": P54_EVIDENCE_STATE,
        "automatic_control_allowed": False,
    }
    values.update(changes)
    return AblationRawSampleFamilyPlanContextConsistency(**values)  # type: ignore[arg-type]


def _verify(
    monkeypatch: pytest.MonkeyPatch,
    *,
    plan: AblationAnalysisPlan | None = None,
    result: bytes | None = None,
    context: AblationRawSampleFamilyPlanContextConsistency | None = None,
):
    plan = plan or _plan()
    result = result or _result(candidate_count=plan.candidate_count, top_k=plan.top_k)
    context = context or _context(plan, result)
    monkeypatch.setattr(
        subject,
        "verify_ablation_raw_sample_family_plan_context_consistency",
        lambda *args, **kwargs: context,
    )
    return subject.verify_ablation_raw_sample_search_policy_consistency(
        context,
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        plan,
        result_artifact=result,
        raw_sample_artifacts={"samples.jsonl": b"{}"},
    )


def test_p55_binds_candidate_universe_and_top_k_deterministically(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _verify(monkeypatch)
    second = _verify(monkeypatch)

    assert first == second
    assert first.candidate_count == 8
    assert first.top_k == 3
    assert first.search_policy_consistency_verified is True
    assert first.automatic_control_allowed is False
    assert len(first.search_policy_binding_sha256) == 64
    assert first.as_dict()["truth_boundary"] == subject.TRUTH_BOUNDARY


def test_p55_accepts_equivalent_utf8_string_result(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    raw = _result()
    context = _context(plan, raw)
    monkeypatch.setattr(
        subject,
        "verify_ablation_raw_sample_family_plan_context_consistency",
        lambda *args, **kwargs: context,
    )
    evidence = subject.verify_ablation_raw_sample_search_policy_consistency(
        context,
        None, None, None, None, None, None, None, None,  # type: ignore[arg-type]
        plan,
        result_artifact=raw.decode("utf-8"),
        raw_sample_artifacts={"samples.jsonl": "{}"},
    )
    assert evidence.result_artifact_sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evidence_state", "wrong", "incompatible evidence_state"),
        ("family_plan_context_consistency_verified", False, "must be verified"),
        ("automatic_control_allowed", True, "cannot authorize automatic control"),
    ],
)
def test_p55_rejects_invalid_p54_state(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object, message: str
) -> None:
    plan = _plan()
    raw = _result()
    context = replace(_context(plan, raw), **{field: value})
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, plan=plan, result=raw, context=context)


def test_p55_rejects_p54_recomputation_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    raw = _result()
    context = _context(plan, raw)
    monkeypatch.setattr(
        subject,
        "verify_ablation_raw_sample_family_plan_context_consistency",
        lambda *args, **kwargs: replace(context, workload_count=context.workload_count + 1),
    )
    with pytest.raises(ValueError, match="does not match the exact result/raw-sample bytes"):
        subject.verify_ablation_raw_sample_search_policy_consistency(
            context,
            None, None, None, None, None, None, None, None,  # type: ignore[arg-type]
            plan,
            result_artifact=raw,
            raw_sample_artifacts={"samples.jsonl": b"{}"},
        )


def test_p55_rejects_result_byte_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    raw = _result()
    context = _context(plan, raw)
    mutated = raw + b"\n"
    monkeypatch.setattr(
        subject,
        "verify_ablation_raw_sample_family_plan_context_consistency",
        lambda *args, **kwargs: context,
    )
    with pytest.raises(ValueError, match="does not bind the supplied result artifact bytes"):
        subject.verify_ablation_raw_sample_search_policy_consistency(
            context,
            None, None, None, None, None, None, None, None,  # type: ignore[arg-type]
            plan,
            result_artifact=mutated,
            raw_sample_artifacts={"samples.jsonl": b"{}"},
        )


def test_p55_rejects_plan_identity_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    raw = _result()
    context = _context(plan, raw)
    drifted = _plan(plan_id="plan-2")
    monkeypatch.setattr(
        subject,
        "verify_ablation_raw_sample_family_plan_context_consistency",
        lambda *args, **kwargs: context,
    )
    with pytest.raises(ValueError, match="plan_id does not match"):
        subject.verify_ablation_raw_sample_search_policy_consistency(
            context,
            None, None, None, None, None, None, None, None,  # type: ignore[arg-type]
            drifted,
            result_artifact=raw,
            raw_sample_artifacts={"samples.jsonl": b"{}"},
        )


@pytest.mark.parametrize(
    ("candidate_count", "top_k", "message"),
    [
        (7, 3, "candidate_count does not match"),
        (8, 2, "top_k does not match"),
        (0, 3, "candidate_count must be a positive integer"),
        (8, 0, "top_k must be a positive integer"),
        (True, 3, "candidate_count must be a positive integer"),
        (8, True, "top_k must be a positive integer"),
        (None, 3, "candidate_count must be a positive integer"),
        (8, None, "top_k must be a positive integer"),
    ],
)
def test_p55_rejects_invalid_or_drifted_search_policy(
    monkeypatch: pytest.MonkeyPatch, candidate_count: object, top_k: object, message: str
) -> None:
    plan = _plan()
    raw = _result(candidate_count=candidate_count, top_k=top_k)
    context = _context(plan, raw)
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, plan=plan, result=raw, context=context)


def test_p55_rejects_top_k_above_candidate_count(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(candidate_count=3, top_k=4)
    raw = _result(candidate_count=3, top_k=4)
    context = _context(plan, raw)
    with pytest.raises(ValueError, match="top_k cannot exceed candidate_count"):
        _verify(monkeypatch, plan=plan, result=raw, context=context)


def test_p55_rejects_result_automatic_control(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    raw = _result(automatic_control=True)
    context = _context(plan, raw)
    with pytest.raises(ValueError, match="automatic_control_allowed=false"):
        _verify(monkeypatch, plan=plan, result=raw, context=context)
