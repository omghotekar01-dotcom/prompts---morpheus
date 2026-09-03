from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

import app.search_quality_ablation_result_raw_sample_family_plan_context as p54
from app.search_quality_ablation_preregistration import AblationAnalysisPlan
from app.search_quality_ablation_result_raw_sample_family_plan import AblationRawSampleFamilyPlanConsistency
from app.search_quality_ablation_result_raw_sample_semantics import AblationRawSampleSemanticConsistency


def _plan(**overrides: object) -> AblationAnalysisPlan:
    values: dict[str, object] = {
        "plan_id": "plan-1",
        "measurement_source_id": "native-benchmark",
        "protocol": "ablation-v1",
        "machine_fingerprint": "machine-a",
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
    source: object = "native-benchmark",
    protocol: object = "ablation-v1",
    machine: object = "machine-a",
    conditions: object = None,
    automatic_control_allowed: object = False,
) -> bytes:
    return json.dumps(
        {
            "raw_sample_evidence": {
                "semantics": {
                    "schema": "morpheus.ablation-raw-sample/v1",
                    "measurement_source": source,
                    "protocol_id": protocol,
                    "machine_fingerprint": machine,
                    "metric": "regret_ratio",
                    "record_count": 3,
                    "condition_ids": conditions if conditions is not None else ["B", "reference", "a"],
                }
            },
            "automatic_control_allowed": automatic_control_allowed,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _raw(*, workload: str = "workload-1") -> dict[str, bytes]:
    records = [
        {
            "schema": "morpheus.ablation-raw-sample/v1",
            "sample_id": f"{condition}-0",
            "condition_id": condition,
            "workload_id": workload,
            "repetition_index": 0,
            "metric": "regret_ratio",
            "value": value,
            "measurement_source": "native-benchmark",
            "protocol_id": "ablation-v1",
            "machine_fingerprint": "machine-a",
        }
        for condition, value in (("reference", 1.0), ("a", 1.1), ("b", 1.2))
    ]
    return {"samples.jsonl": ("\n".join(json.dumps(item, sort_keys=True) for item in records) + "\n").encode()}


def _family_plan(result: bytes, plan: AblationAnalysisPlan, **overrides: object) -> AblationRawSampleFamilyPlanConsistency:
    values: dict[str, object] = {
        "family_correction_sha256": "11" * 32,
        "result_artifact_sha256": hashlib.sha256(result).hexdigest(),
        "plan_id": plan.plan_id,
        "plan_sha256": plan.sha256(),
        "reference_condition_id": "reference",
        "family_size": 2,
        "family_wise_alpha": "0.05",
        "normalized_family_members": ("a", "b"),
        "family_plan_binding_sha256": "22" * 32,
        "family_plan_consistency_verified": True,
    }
    values.update(overrides)
    return AblationRawSampleFamilyPlanConsistency(**values)  # type: ignore[arg-type]


def _semantics(**overrides: object) -> AblationRawSampleSemanticConsistency:
    values: dict[str, object] = {
        "raw_sample_binding_sha256": "33" * 32,
        "raw_sample_inventory_sha256": "44" * 32,
        "semantic_context_sha256": "55" * 32,
        "semantic_verification_sha256": "66" * 32,
        "raw_sample_artifact_count": 1,
        "raw_sample_record_count": 3,
        "condition_count": 3,
        "semantics_verified": True,
    }
    values.update(overrides)
    return AblationRawSampleSemanticConsistency(**values)  # type: ignore[arg-type]


def _verify(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: bytes | None = None,
    raw: dict[str, bytes] | None = None,
    plan: AblationAnalysisPlan | None = None,
    family_plan: AblationRawSampleFamilyPlanConsistency | None = None,
    semantics: AblationRawSampleSemanticConsistency | None = None,
):
    result = _artifact() if result is None else result
    raw = _raw() if raw is None else raw
    plan = _plan() if plan is None else plan
    family_plan = _family_plan(result, plan) if family_plan is None else family_plan
    semantics = _semantics() if semantics is None else semantics
    monkeypatch.setattr(p54, "verify_ablation_raw_sample_family_plan_consistency", lambda *args, **kwargs: family_plan)
    monkeypatch.setattr(p54, "verify_ablation_raw_sample_semantics", lambda *args, **kwargs: semantics)
    placeholder = SimpleNamespace()
    return p54.verify_ablation_raw_sample_family_plan_context_consistency(
        family_plan,
        placeholder,
        placeholder,
        placeholder,
        placeholder,
        placeholder,
        semantics,
        placeholder,
        placeholder,
        plan,
        result_artifact=result,
        raw_sample_artifacts=raw,
    )


def test_p54_binds_raw_sample_context_and_complete_coverage_to_p32_deterministically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _verify(monkeypatch)
    second = _verify(monkeypatch)
    equivalent = _verify(monkeypatch, result=_artifact(conditions=["a", "REFERENCE", "b"]))
    assert first.family_plan_context_consistency_verified is True
    assert first.automatic_control_allowed is False
    assert first.measurement_source_id == "native-benchmark"
    assert first.protocol == "ablation-v1"
    assert first.machine_fingerprint == "machine-a"
    assert first.workload_count == 1
    assert first.normalized_condition_ids == ("a", "b", "reference")
    assert first.family_plan_context_sha256 == second.family_plan_context_sha256
    assert equivalent.normalized_condition_ids == first.normalized_condition_ids
    assert equivalent.family_plan_context_sha256 != first.family_plan_context_sha256


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evidence_state", "WRONG", "incompatible evidence_state"),
        ("family_plan_consistency_verified", False, "must be verified"),
        ("automatic_control_allowed", True, "cannot authorize automatic control"),
    ],
)
def test_p54_rejects_incompatible_p53_evidence(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object, message: str
) -> None:
    result = _artifact()
    plan = _plan()
    family_plan = replace(_family_plan(result, plan), **{field: value})
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, result=result, plan=plan, family_plan=family_plan)


def test_p54_rejects_p53_recomputation_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _artifact()
    plan = _plan()
    family_plan = _family_plan(result, plan)
    semantics = _semantics()
    monkeypatch.setattr(
        p54,
        "verify_ablation_raw_sample_family_plan_consistency",
        lambda *args, **kwargs: replace(family_plan, family_plan_binding_sha256="77" * 32),
    )
    monkeypatch.setattr(p54, "verify_ablation_raw_sample_semantics", lambda *args, **kwargs: semantics)
    placeholder = SimpleNamespace()
    with pytest.raises(ValueError, match="does not match the exact result/raw-sample bytes"):
        p54.verify_ablation_raw_sample_family_plan_context_consistency(
            family_plan,
            placeholder,
            placeholder,
            placeholder,
            placeholder,
            placeholder,
            semantics,
            placeholder,
            placeholder,
            plan,
            result_artifact=result,
            raw_sample_artifacts=_raw(),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evidence_state", "WRONG", "incompatible evidence_state"),
        ("semantics_verified", False, "must be verified"),
        ("automatic_control_allowed", True, "cannot authorize automatic control"),
    ],
)
def test_p54_rejects_incompatible_p47_evidence(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, semantics=replace(_semantics(), **{field: value}))


def test_p54_rejects_p47_recomputation_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _artifact()
    raw = _raw()
    plan = _plan()
    family_plan = _family_plan(result, plan)
    semantics = _semantics()
    monkeypatch.setattr(p54, "verify_ablation_raw_sample_family_plan_consistency", lambda *args, **kwargs: family_plan)
    monkeypatch.setattr(
        p54,
        "verify_ablation_raw_sample_semantics",
        lambda *args, **kwargs: replace(semantics, semantic_verification_sha256="88" * 32),
    )
    placeholder = SimpleNamespace()
    with pytest.raises(ValueError, match="semantic evidence does not match"):
        p54.verify_ablation_raw_sample_family_plan_context_consistency(
            family_plan,
            placeholder,
            placeholder,
            placeholder,
            placeholder,
            placeholder,
            semantics,
            placeholder,
            placeholder,
            plan,
            result_artifact=result,
            raw_sample_artifacts=raw,
        )


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (_artifact(source="other"), "measurement source"),
        (_artifact(protocol="other"), "protocol"),
        (_artifact(machine="other"), "machine fingerprint"),
        (_artifact(conditions=["reference", "a", "c"]), "condition coverage"),
    ],
)
def test_p54_rejects_raw_sample_plan_context_drift(
    monkeypatch: pytest.MonkeyPatch, result: bytes, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, result=result)


def test_p54_rejects_duplicate_normalized_condition_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="distinct after normalization"):
        _verify(monkeypatch, result=_artifact(conditions=["reference", "a", "A"]))


def test_p54_rejects_raw_sample_workload_cardinality_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(workload_count=2)
    result = _artifact()
    family_plan = _family_plan(result, plan)
    with pytest.raises(ValueError, match="workload cardinality"):
        _verify(monkeypatch, result=result, plan=plan, family_plan=family_plan)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"result_artifact_sha256": "99" * 32}, "supplied result artifact bytes"),
        ({"plan_id": "other-plan"}, "plan_id"),
        ({"plan_sha256": "aa" * 32}, "plan content"),
    ],
)
def test_p54_rejects_p53_result_or_plan_identity_drift(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, object], message: str
) -> None:
    result = _artifact()
    plan = _plan()
    family_plan = _family_plan(result, plan, **overrides)
    with pytest.raises(ValueError, match=message):
        _verify(monkeypatch, result=result, plan=plan, family_plan=family_plan)


def test_p54_rejects_reference_ablation_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(reference_label="A")
    result = _artifact(conditions=["a", "b"])
    family_plan = _family_plan(result, plan)
    with pytest.raises(ValueError, match="reference and ablation labels"):
        _verify(monkeypatch, result=result, plan=plan, family_plan=family_plan)


@pytest.mark.parametrize(
    "result",
    [
        b"not-json",
        json.dumps({"raw_sample_evidence": {}, "automatic_control_allowed": False}).encode(),
        json.dumps({"raw_sample_evidence": {"semantics": {}}, "automatic_control_allowed": True}).encode(),
    ],
)
def test_p54_rejects_malformed_or_control_authorizing_result(
    monkeypatch: pytest.MonkeyPatch, result: bytes
) -> None:
    plan = _plan()
    family_plan = _family_plan(result, plan)
    with pytest.raises(ValueError):
        _verify(monkeypatch, result=result, plan=plan, family_plan=family_plan)
