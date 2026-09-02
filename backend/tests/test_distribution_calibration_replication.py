from __future__ import annotations

from dataclasses import replace

import pytest

from app.distribution_calibration_holdout import (
    DistributionCalibrationHoldoutPoint,
    evaluate_distribution_calibration_holdout,
)
from app.distribution_calibration_replication import evaluate_distribution_calibration_replication


def _holdout(machine: str, measured_scale: float = 1.0, *, protocol: str = "morpheus-replication-v1"):
    points = [
        DistributionCalibrationHoldoutPoint(
            holdout_id=f"{machine}-h1",
            measurement_source_id=f"{machine}-source-1",
            primitive="robin_hood_hash",
            implementation_id="morpheus.RobinHoodHashIndex.v1",
            operation="point_lookup",
            distribution_signature="hotspot(f=0.1,p=0.8)",
            protocol=protocol,
            machine_fingerprint=machine,
            predicted_ns_per_op=20.0,
            measured_ns_per_op=22.0 * measured_scale,
        ),
        DistributionCalibrationHoldoutPoint(
            holdout_id=f"{machine}-h2",
            measurement_source_id=f"{machine}-source-2",
            primitive="robin_hood_hash",
            implementation_id="morpheus.RobinHoodHashIndex.v1",
            operation="point_lookup",
            distribution_signature="zipf(theta=0.99)",
            protocol=protocol,
            machine_fingerprint=machine,
            predicted_ns_per_op=30.0,
            measured_ns_per_op=33.0 * measured_scale,
        ),
    ]
    return evaluate_distribution_calibration_holdout(
        points,
        calibration_source_ids=[f"{machine}-calibration"],
        max_allowed_mean_ape=0.25,
        max_allowed_worst_ape=0.25,
    )


def test_cross_machine_replication_passes_only_declared_spread_and_never_authorizes_control() -> None:
    report = evaluate_distribution_calibration_replication(
        [_holdout("machine-a"), _holdout("machine-b", 1.02)],
        max_allowed_machine_mape_spread=0.05,
    )
    assert report.replication_passed is True
    assert report.machine_count == 2
    assert report.all_holdouts_accepted is True
    payload = report.as_dict()
    assert payload["automatic_control_allowed"] is False
    assert payload["evidence_state"] == "METHODOLOGY_ONLY_CALLER_SUPPLIED_CROSS_MACHINE_REPLICATION"
    assert "does not prove independent laboratories" in payload["truth_boundary"]


def test_cross_machine_replication_can_fail_declared_spread_without_hiding_metrics() -> None:
    report = evaluate_distribution_calibration_replication(
        [_holdout("machine-a"), _holdout("machine-b", 1.15)],
        max_allowed_machine_mape_spread=0.01,
    )
    assert report.replication_passed is False
    assert report.machine_mape_spread > 0.01
    assert report.max_machine_mape >= report.min_machine_mape


def test_cross_machine_replication_rejects_duplicate_machine_or_single_machine() -> None:
    first = _holdout("machine-a")
    with pytest.raises(ValueError, match="at most one held-out report per machine"):
        evaluate_distribution_calibration_replication(
            [first, first],
            max_allowed_machine_mape_spread=0.1,
        )

    with pytest.raises(ValueError, match="at least 2 distinct machine"):
        evaluate_distribution_calibration_replication(
            [first],
            max_allowed_machine_mape_spread=0.1,
        )


def test_cross_machine_replication_rejects_mixed_measurement_protocols() -> None:
    with pytest.raises(ValueError, match="one measurement protocol"):
        evaluate_distribution_calibration_replication(
            [_holdout("machine-a"), _holdout("machine-b", protocol="other-protocol")],
            max_allowed_machine_mape_spread=0.1,
        )


def test_cross_machine_replication_rejects_constituent_holdout_that_failed_its_own_gate() -> None:
    failed = replace(_holdout("machine-b"), acceptance_passed=False)
    with pytest.raises(ValueError, match="every constituent held-out report"):
        evaluate_distribution_calibration_replication(
            [_holdout("machine-a"), failed],
            max_allowed_machine_mape_spread=0.1,
        )


def test_cross_machine_replication_rejects_any_attempt_to_promote_holdout_to_control_authority() -> None:
    promoted = replace(_holdout("machine-b"), automatic_control_allowed=True)
    with pytest.raises(ValueError, match="cannot authorize automatic control"):
        evaluate_distribution_calibration_replication(
            [_holdout("machine-a"), promoted],
            max_allowed_machine_mape_spread=0.1,
        )


def test_cross_machine_replication_is_deterministic_for_identical_inputs() -> None:
    inputs = [_holdout("machine-a"), _holdout("machine-b", 1.02)]
    first = evaluate_distribution_calibration_replication(
        inputs,
        max_allowed_machine_mape_spread=0.05,
    )
    second = evaluate_distribution_calibration_replication(
        inputs,
        max_allowed_machine_mape_spread=0.05,
    )
    assert first.as_dict() == second.as_dict()
