from __future__ import annotations

from app.research_suite import (
    PairedObservation,
    analyze_paired_measurements,
    freeze_experiment_matrix,
)


def test_experiment_matrix_is_deterministic_independent_of_axis_declaration_order() -> None:
    first = freeze_experiment_matrix(
        study_id="rq3-search-quality",
        hypothesis="beam preserves low regret while evaluating fewer candidates",
        metric="model_score_regret",
        lower_is_better=True,
        repetitions=5,
        seeds=[1337, 2027],
        axes={
            "beam_width": [8, 32],
            "workload": ["point-heavy", "mixed"],
        },
    )
    second = freeze_experiment_matrix(
        study_id="rq3-search-quality",
        hypothesis="beam preserves low regret while evaluating fewer candidates",
        metric="model_score_regret",
        lower_is_better=True,
        repetitions=5,
        seeds=[1337, 2027],
        axes={
            "workload": ["point-heavy", "mixed"],
            "beam_width": [8, 32],
        },
    )

    assert first.manifest_sha256 == second.manifest_sha256
    assert [item.experiment_id for item in first.experiments] == [
        item.experiment_id for item in second.experiments
    ]
    assert len(first.experiments) == 4
    assert len({item.experiment_id for item in first.experiments}) == 4
    assert all(item.evidence_state == "FROZEN_EXPERIMENT_PLAN_NOT_EXECUTED" for item in first.experiments)


def test_experiment_matrix_rejects_unbounded_expansion() -> None:
    try:
        freeze_experiment_matrix(
            study_id="too-large",
            hypothesis="guardrail",
            metric="latency",
            lower_is_better=True,
            repetitions=1,
            seeds=[1],
            axes={"a": range(20), "b": range(20)},
            max_experiments=100,
        )
    except ValueError as exc:
        assert "more than 100 combinations" in str(exc)
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("matrix expansion guardrail did not fire")


def test_paired_analysis_is_direction_safe_and_bootstrap_reproducible() -> None:
    observations = [
        PairedObservation("w1", baseline=100.0, treatment=80.0),
        PairedObservation("w2", baseline=110.0, treatment=90.0),
        PairedObservation("w3", baseline=95.0, treatment=85.0),
        PairedObservation("w4", baseline=120.0, treatment=100.0),
    ]
    first = analyze_paired_measurements(
        metric="latency_us",
        observations=observations,
        lower_is_better=True,
        bootstrap_rounds=500,
        bootstrap_seed=99,
    )
    second = analyze_paired_measurements(
        metric="latency_us",
        observations=observations,
        lower_is_better=True,
        bootstrap_rounds=500,
        bootstrap_seed=99,
    )

    assert first.mean_improvement > 0
    assert first.wins == 4
    assert first.losses == 0
    assert first.win_rate_excluding_ties == 1.0
    assert first.bootstrap_mean_improvement_ci == second.bootstrap_mean_improvement_ci
    assert first.exact_sign_test_p_two_sided == 0.125
    assert first.evidence_state == "ANALYZED_CALLER_SUPPLIED_PAIRED_MEASUREMENTS"


def test_higher_is_better_metrics_keep_positive_improvement_semantics() -> None:
    report = analyze_paired_measurements(
        metric="throughput_ops_s",
        observations=[
            PairedObservation("a", baseline=1000, treatment=1200),
            PairedObservation("b", baseline=900, treatment=990),
            PairedObservation("c", baseline=1100, treatment=1100),
        ],
        lower_is_better=False,
        bootstrap_rounds=300,
    )
    assert report.mean_improvement > 0
    assert report.wins == 2
    assert report.ties == 1
    assert report.losses == 0
