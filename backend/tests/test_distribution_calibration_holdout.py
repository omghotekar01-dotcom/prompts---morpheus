from __future__ import annotations

import pytest

from app.distribution_calibration_holdout import (
    DistributionCalibrationHoldoutPoint,
    evaluate_distribution_calibration_holdout,
)


def _point(
    holdout_id: str,
    source: str,
    distribution: str,
    predicted: float,
    measured: float,
    *,
    protocol: str = "morpheus-distribution-calibration-v1",
    machine: str = "machine-a",
) -> DistributionCalibrationHoldoutPoint:
    return DistributionCalibrationHoldoutPoint(
        holdout_id=holdout_id,
        measurement_source_id=source,
        primitive="robin_hood_hash",
        implementation_id="morpheus.RobinHoodHashIndex.v1",
        operation="point_lookup",
        distribution_signature=distribution,
        protocol=protocol,
        machine_fingerprint=machine,
        predicted_ns_per_op=predicted,
        measured_ns_per_op=measured,
    )


def _fixture() -> list[DistributionCalibrationHoldoutPoint]:
    return [
        _point("h1", "holdout-seed-2001", "hotspot(f=0.1,p=0.8)", 20.0, 22.0),
        _point("h2", "holdout-seed-2002", "zipf(theta=0.99)", 30.0, 33.0),
        _point("h3", "holdout-seed-2003", "hotspot(f=0.1,p=0.8)", 21.0, 20.0),
        _point("h4", "holdout-seed-2004", "zipf(theta=0.99)", 32.0, 31.0),
    ]


def test_holdout_reports_declared_acceptance_without_authorizing_control() -> None:
    report = evaluate_distribution_calibration_holdout(
        _fixture(),
        calibration_source_ids=["calibration-seed-1337", "calibration-seed-1338"],
        max_allowed_mean_ape=0.10,
        max_allowed_worst_ape=0.12,
    )
    assert report.acceptance_passed is True
    assert report.point_count == 4
    assert report.distribution_count == 2
    payload = report.as_dict()
    assert payload["automatic_control_allowed"] is False
    assert payload["evidence_state"] == "METHODOLOGY_ONLY_CALLER_SUPPLIED_HELDOUT_DISTRIBUTION_MEASUREMENTS"
    assert "does not prove measurement independence" in payload["truth_boundary"]


def test_holdout_can_fail_declared_acceptance_without_hiding_metrics() -> None:
    report = evaluate_distribution_calibration_holdout(
        _fixture(),
        calibration_source_ids=["calibration-seed-1337"],
        max_allowed_mean_ape=0.01,
        max_allowed_worst_ape=0.01,
    )
    assert report.acceptance_passed is False
    assert report.mean_absolute_percentage_error > 0.01
    assert report.max_absolute_percentage_error > 0.01


def test_holdout_rejects_calibration_source_leakage() -> None:
    with pytest.raises(ValueError, match="source leakage"):
        evaluate_distribution_calibration_holdout(
            _fixture(),
            calibration_source_ids=["holdout-seed-2001"],
            max_allowed_mean_ape=0.5,
            max_allowed_worst_ape=0.5,
        )


def test_holdout_rejects_mixed_protocol_or_machine_campaigns() -> None:
    mixed_protocol = _fixture()
    mixed_protocol[-1] = _point(
        "h4", "holdout-seed-2004", "zipf(theta=0.99)", 32.0, 31.0, protocol="other"
    )
    with pytest.raises(ValueError, match="one measurement protocol"):
        evaluate_distribution_calibration_holdout(
            mixed_protocol,
            calibration_source_ids=["train"],
            max_allowed_mean_ape=0.5,
            max_allowed_worst_ape=0.5,
        )

    mixed_machine = _fixture()
    mixed_machine[-1] = _point(
        "h4", "holdout-seed-2004", "zipf(theta=0.99)", 32.0, 31.0, machine="machine-b"
    )
    with pytest.raises(ValueError, match="one machine fingerprint"):
        evaluate_distribution_calibration_holdout(
            mixed_machine,
            calibration_source_ids=["train"],
            max_allowed_mean_ape=0.5,
            max_allowed_worst_ape=0.5,
        )


def test_holdout_requires_multiple_nonuniform_distributions() -> None:
    one_distribution = [
        _point("h1", "holdout-1", "zipf(theta=0.99)", 10.0, 10.0),
        _point("h2", "holdout-2", "zipf(theta=0.99)", 11.0, 11.0),
    ]
    with pytest.raises(ValueError, match="distinct nonuniform distributions"):
        evaluate_distribution_calibration_holdout(
            one_distribution,
            calibration_source_ids=["train"],
            max_allowed_mean_ape=0.1,
            max_allowed_worst_ape=0.1,
        )

    uniform = _fixture()
    uniform[0] = _point("h1", "holdout-seed-2001", "uniform", 20.0, 22.0)
    with pytest.raises(ValueError, match="must be nonuniform"):
        evaluate_distribution_calibration_holdout(
            uniform,
            calibration_source_ids=["train"],
            max_allowed_mean_ape=0.5,
            max_allowed_worst_ape=0.5,
        )


def test_holdout_report_is_deterministic_for_identical_inputs() -> None:
    kwargs = {
        "calibration_source_ids": ["train-b", "train-a"],
        "max_allowed_mean_ape": 0.2,
        "max_allowed_worst_ape": 0.2,
    }
    first = evaluate_distribution_calibration_holdout(_fixture(), **kwargs)
    second = evaluate_distribution_calibration_holdout(_fixture(), **kwargs)
    assert first.as_dict() == second.as_dict()
