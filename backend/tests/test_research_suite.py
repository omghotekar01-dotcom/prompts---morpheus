from __future__ import annotations

from app.research_suite import (
    PairedObservation,
    analyze_paired_measurements,
    freeze_experiment_matrix,
    holm_bonferroni,
)


def test_holm_bonferroni_is_step_down_monotone_and_order_independent() -> None:
    raw = {"rq5": 0.04, "rq2": 0.001, "rq4": 0.03, "rq3": 0.01}
    first = holm_bonferroni(raw, alpha=0.05)
    second = holm_bonferroni(dict(reversed(list(raw.items()))), alpha=0.05)
    assert first == second
    assert first["rq2"]["reject_null"] is True
    assert first["rq3"]["reject_null"] is True
    assert first["rq4"]["reject_null"] is False
    assert first["rq5"]["reject_null"] is False
    ordered_adjusted = [first[key]["adjusted_p"] for key in ("rq2", "rq3", "rq4", "rq5")]
    assert ordered_adjusted == sorted(ordered_adjusted)


def test_holm_bonferroni_rejects_invalid_inputs() -> None:
    for payload in ({}, {"bad": -0.1}, {"bad": 1.1}, {"bad": float("nan")}):
        try:
            holm_bonferroni(payload)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid Holm input accepted: {payload!r}")


def test_experiment_matrix_is_deterministic_independent_of_axis_declaration_order() -> None:
    first = freeze_experiment_matrix(study_id="rq3-search-quality", hypothesis="beam preserves low regret while evaluating fewer candidates", metric="model_score_regret", lower_is_better=True, repetitions=5, seeds=[1337, 2027], axes={"beam_width": [8, 32], "workload": ["point-heavy", "mixed"]})
    second = freeze_experiment_matrix(study_id="rq3-search-quality", hypothesis="beam preserves low regret while evaluating fewer candidates", metric="model_score_regret", lower_is_better=True, repetitions=5, seeds=[1337, 2027], axes={"workload": ["point-heavy", "mixed"], "beam_width": [8, 32]})
    assert first.manifest_sha256 == second.manifest_sha256
    assert [item.experiment_id for item in first.experiments] == [item.experiment_id for item in second.experiments]
    assert len(first.experiments) == 4
    assert len({item.experiment_id for item in first.experiments}) == 4
    assert all(item.evidence_state == "FROZEN_EXPERIMENT_PLAN_NOT_EXECUTED" for item in first.experiments)


def test_experiment_matrix_rejects_unbounded_expansion() -> None:
    try:
        freeze_experiment_matrix(study_id="too-large", hypothesis="guardrail", metric="latency", lower_is_better=True, repetitions=1, seeds=[1], axes={"a": range(20), "b": range(20)}, max_experiments=100)
    except ValueError as exc:
        assert "more than 100 combinations" in str(exc)
    else:
        raise AssertionError("matrix expansion guardrail did not fire")


def test_paired_analysis_is_direction_safe_and_bootstrap_reproducible() -> None:
    observations = [PairedObservation("w1",100.0,80.0), PairedObservation("w2",110.0,90.0), PairedObservation("w3",95.0,85.0), PairedObservation("w4",120.0,100.0)]
    first = analyze_paired_measurements(metric="latency_us", observations=observations, lower_is_better=True, bootstrap_rounds=500, bootstrap_seed=99)
    second = analyze_paired_measurements(metric="latency_us", observations=observations, lower_is_better=True, bootstrap_rounds=500, bootstrap_seed=99)
    assert first.mean_improvement > 0
    assert first.wins == 4 and first.losses == 0 and first.win_rate_excluding_ties == 1.0
    assert first.bootstrap_mean_improvement_ci == second.bootstrap_mean_improvement_ci
    assert first.exact_sign_test_p_two_sided == 0.125
    assert first.evidence_state == "ANALYZED_CALLER_SUPPLIED_PAIRED_MEASUREMENTS"


def test_higher_is_better_metrics_keep_positive_improvement_semantics() -> None:
    report = analyze_paired_measurements(metric="throughput_ops_s", observations=[PairedObservation("a",1000,1200),PairedObservation("b",900,990),PairedObservation("c",1100,1100)], lower_is_better=False, bootstrap_rounds=300)
    assert report.mean_improvement > 0
    assert report.wins == 2 and report.ties == 1 and report.losses == 0
