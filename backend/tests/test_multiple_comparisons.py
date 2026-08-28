from __future__ import annotations

import pytest

from app.multiple_comparisons import holm_bonferroni


def test_holm_bonferroni_is_deterministic_and_step_down_correct() -> None:
    first = holm_bonferroni(
        {
            "rq4-composition": 0.04,
            "rq1-end-to-end": 0.001,
            "rq3-search": 0.03,
            "rq2-calibration": 0.008,
        },
        alpha=0.05,
    )
    second = holm_bonferroni(
        {
            "rq2-calibration": 0.008,
            "rq3-search": 0.03,
            "rq1-end-to-end": 0.001,
            "rq4-composition": 0.04,
        },
        alpha=0.05,
    )

    assert first.as_dict() == second.as_dict()
    assert [item.label for item in first.hypotheses] == [
        "rq1-end-to-end",
        "rq2-calibration",
        "rq3-search",
        "rq4-composition",
    ]
    assert [item.rejected for item in first.hypotheses] == [True, True, False, False]
    assert [item.adjusted_p for item in first.hypotheses] == pytest.approx([0.004, 0.024, 0.06, 0.06])
    assert first.hypotheses[0].threshold == pytest.approx(0.0125)
    assert first.hypotheses[1].threshold == pytest.approx(0.05 / 3)
    assert first.evidence_state == "CORRECTED_CALLER_SUPPLIED_P_VALUES"


def test_holm_adjusted_p_values_are_monotone_even_with_ties() -> None:
    report = holm_bonferroni({"b": 0.01, "a": 0.01, "c": 0.20})
    adjusted = [item.adjusted_p for item in report.hypotheses]
    assert adjusted == sorted(adjusted)
    assert [item.label for item in report.hypotheses[:2]] == ["a", "b"]


def test_holm_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        holm_bonferroni({})
    with pytest.raises(ValueError):
        holm_bonferroni({"x": -0.1})
    with pytest.raises(ValueError):
        holm_bonferroni({"x": 1.1})
    with pytest.raises(ValueError):
        holm_bonferroni({"": 0.1})
    with pytest.raises(ValueError):
        holm_bonferroni({"x": 0.1}, alpha=1.0)
