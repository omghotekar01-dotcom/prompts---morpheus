from __future__ import annotations

from app.access_trace_validation import evaluate_synthetic_classifier


def test_synthetic_classifier_evaluation_is_deterministic_and_not_promotable() -> None:
    first = evaluate_synthetic_classifier(
        seeds=(7,),
        sample_counts=(500,),
        domain_sizes=(100,),
    ).as_dict()
    second = evaluate_synthetic_classifier(
        seeds=(7,),
        sample_counts=(500,),
        domain_sizes=(100,),
    ).as_dict()

    assert first == second
    assert first["schema"] == "morpheus-access-trace-classifier-synthetic-evaluation-v1"
    assert first["case_count"] == 9
    assert 0.0 <= first["overall_accuracy"] <= 1.0
    assert first["eligible_for_runtime_automatic_promotion"] is False
    assert "not real-workload validation" in first["truth_boundary"]


def test_synthetic_classifier_reports_full_confusion_matrix_and_family_accuracy() -> None:
    payload = evaluate_synthetic_classifier(
        seeds=(17, 19),
        sample_counts=(1000,),
        domain_sizes=(100,),
    ).as_dict()
    labels = {"uniform", "sequential", "hotspot", "zipf"}

    assert set(payload["confusion"]) == labels
    assert all(set(row) == labels for row in payload["confusion"].values())
    assert set(payload["per_family_accuracy"]) == labels
    assert payload["per_family_accuracy"]["sequential"] == 1.0
    assert sum(sum(row.values()) for row in payload["confusion"].values()) == payload["case_count"]
    assert payload["evidence_state"] == "SYNTHETIC_GENERATOR_CLASSIFICATION_EVALUATION_NOT_REAL_TRACE_VALIDATION"
