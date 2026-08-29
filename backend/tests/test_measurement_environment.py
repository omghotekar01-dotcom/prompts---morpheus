from __future__ import annotations

import hashlib
import json

import pytest

from app import measurement_environment as env
from app.measurement_environment_evidence import validate_measurement_environment_record_bytes


def _canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _snapshot(*, captured_at: str, github_actions: bool = False, affinity: list[int] | None = None) -> dict:
    core = {
        "schema": env.SNAPSHOT_SCHEMA,
        "captured_at": captured_at,
        "platform": "Linux",
        "logical_cpu_count": 8,
        "process_affinity": list(range(8)) if affinity is None else affinity,
        "load_average": {
            "one_minute": 0.8,
            "five_minutes": 0.4,
            "fifteen_minutes": 0.2,
            "one_minute_per_logical_cpu": 0.1,
        },
        "linux_scaling_governors": {"cpu0": "performance", "cpu1": "performance"},
        "linux_frequency_summary": {
            "observed_cpu_count": 2,
            "min_khz": 2_000_000,
            "mean_khz": 2_500_000.0,
            "max_khz": 3_000_000,
        },
        "windows_active_power_scheme": None,
        "thermal_summary": {
            "sensor_count": 2,
            "min_celsius": 40.0,
            "mean_celsius": 45.0,
            "max_celsius": 50.0,
        },
        "github_actions": github_actions,
        "evidence_state": env.SNAPSHOT_EVIDENCE_STATE,
        "truth_boundary": env._SNAPSHOT_TRUTH_BOUNDARY,
    }
    return {**core, "snapshot_sha256": _canonical(core)}


def _rehash_snapshot(snapshot: dict) -> None:
    snapshot["snapshot_sha256"] = _canonical(
        {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    )


def _rehash_record(record: dict) -> None:
    record["record_sha256"] = _canonical(
        {key: value for key, value in record.items() if key != "record_sha256"}
    )


def _record(*, github_actions: bool = False, resumed: bool = False) -> dict:
    start = _snapshot(captured_at="2026-08-29T09:00:00+00:00", github_actions=github_actions)
    end = _snapshot(captured_at="2026-08-29T09:10:00+00:00", github_actions=github_actions)
    covered = [f"mx-{index:02d}" for index in range(2 if resumed else 24)]
    return env.build_measurement_environment_record(
        start,
        end,
        campaign_sha256="a" * 64,
        machine_fingerprint_sha256="b" * 64,
        covered_experiment_ids=covered,
        planned_experiments=24,
        resumed_from_campaign_sha256="c" * 64 if resumed else None,
        operator_note="  controlled local RQ7 run  ",
    )


def test_full_local_environment_record_is_content_hashed_and_release_valid() -> None:
    record = _record()
    env.validate_measurement_environment_record(record)
    structural = validate_measurement_environment_record_bytes(json.dumps(record).encode("utf-8"))

    assert structural.valid is True
    assert record["evidence_state"] == env.LOCAL_RECORD_EVIDENCE_STATE
    assert record["coverage"]["covered_experiment_count"] == 24
    assert record["coverage"]["complete_single_invocation_coverage"] is True
    assert record["coverage"]["resumed_from_campaign_sha256"] is None
    assert record["observed_stability"] == {
        "process_affinity_stable": True,
        "linux_governors_stable": True,
        "windows_power_scheme_stable": False,
        "same_logical_cpu_count": True,
    }
    assert record["operator_note"] == "controlled local RQ7 run"
    assert len(record["record_sha256"]) == 64


def test_resumed_environment_record_covers_only_new_cells_and_is_not_complete() -> None:
    record = _record(resumed=True)
    env.validate_measurement_environment_record(record)

    assert record["coverage"]["covered_experiment_count"] == 2
    assert record["coverage"]["complete_single_invocation_coverage"] is False
    assert record["coverage"]["resumed_from_campaign_sha256"] == "c" * 64


def test_ci_snapshot_pair_cannot_masquerade_as_local_environment_evidence() -> None:
    record = _record(github_actions=True)
    env.validate_measurement_environment_record(record)

    assert record["evidence_state"] == env.CI_RECORD_EVIDENCE_STATE
    record["evidence_state"] = env.LOCAL_RECORD_EVIDENCE_STATE
    _rehash_record(record)
    with pytest.raises(ValueError, match="evidence_state"):
        env.validate_measurement_environment_record(record)


def test_nested_snapshot_tampering_is_rejected_even_when_outer_record_is_rehashed() -> None:
    record = _record()
    record["start_snapshot"]["linux_frequency_summary"]["mean_khz"] = 9_999_999
    _rehash_record(record)

    with pytest.raises(ValueError, match="snapshot hash mismatch"):
        env.validate_measurement_environment_record(record)


def test_self_consistent_forged_stability_flags_are_recomputed_and_rejected() -> None:
    record = _record()
    record["observed_stability"]["process_affinity_stable"] = False
    _rehash_record(record)

    with pytest.raises(ValueError, match="observed stability"):
        env.validate_measurement_environment_record(record)


def test_build_rejects_end_timestamp_before_start() -> None:
    start = _snapshot(captured_at="2026-08-29T09:10:00+00:00")
    end = _snapshot(captured_at="2026-08-29T09:00:00+00:00")

    with pytest.raises(ValueError, match="predates"):
        env.build_measurement_environment_record(
            start,
            end,
            campaign_sha256="a" * 64,
            machine_fingerprint_sha256="b" * 64,
            covered_experiment_ids=["mx-01"],
            planned_experiments=24,
        )


def test_self_hashed_snapshot_with_wrong_normalized_load_is_rejected() -> None:
    start = _snapshot(captured_at="2026-08-29T09:00:00+00:00")
    start["load_average"]["one_minute_per_logical_cpu"] = 0.9
    _rehash_snapshot(start)
    end = _snapshot(captured_at="2026-08-29T09:01:00+00:00")

    with pytest.raises(ValueError, match="normalized load"):
        env.build_measurement_environment_record(
            start,
            end,
            campaign_sha256="a" * 64,
            machine_fingerprint_sha256="b" * 64,
            covered_experiment_ids=["mx-01"],
            planned_experiments=24,
        )


def test_self_hashed_snapshot_with_invalid_frequency_order_is_rejected() -> None:
    start = _snapshot(captured_at="2026-08-29T09:00:00+00:00")
    start["linux_frequency_summary"]["mean_khz"] = 4_000_000
    _rehash_snapshot(start)
    end = _snapshot(captured_at="2026-08-29T09:01:00+00:00")

    with pytest.raises(ValueError, match="frequency summary ordering"):
        env.build_measurement_environment_record(
            start,
            end,
            campaign_sha256="a" * 64,
            machine_fingerprint_sha256="b" * 64,
            covered_experiment_ids=["mx-01"],
            planned_experiments=24,
        )


def test_self_hashed_snapshot_with_unphysical_thermal_summary_is_rejected() -> None:
    start = _snapshot(captured_at="2026-08-29T09:00:00+00:00")
    start["thermal_summary"]["max_celsius"] = 500.0
    _rehash_snapshot(start)
    end = _snapshot(captured_at="2026-08-29T09:01:00+00:00")

    with pytest.raises(ValueError, match="physical range"):
        env.build_measurement_environment_record(
            start,
            end,
            campaign_sha256="a" * 64,
            machine_fingerprint_sha256="b" * 64,
            covered_experiment_ids=["mx-01"],
            planned_experiments=24,
        )


def test_build_rejects_placeholder_hashes_and_mixed_ci_identity() -> None:
    start = _snapshot(captured_at="2026-08-29T09:00:00+00:00", github_actions=False)
    end = _snapshot(captured_at="2026-08-29T09:01:00+00:00", github_actions=True)

    with pytest.raises(ValueError, match="campaign_sha256"):
        env.build_measurement_environment_record(
            start,
            start,
            campaign_sha256="0" * 64,
            machine_fingerprint_sha256="b" * 64,
            covered_experiment_ids=["mx-01"],
            planned_experiments=24,
        )
    with pytest.raises(ValueError, match="CI identity"):
        env.build_measurement_environment_record(
            start,
            end,
            campaign_sha256="a" * 64,
            machine_fingerprint_sha256="b" * 64,
            covered_experiment_ids=["mx-01"],
            planned_experiments=24,
        )


def test_operator_note_is_bounded() -> None:
    start = _snapshot(captured_at="2026-08-29T09:00:00+00:00")
    end = _snapshot(captured_at="2026-08-29T09:01:00+00:00")
    with pytest.raises(ValueError, match="4096"):
        env.build_measurement_environment_record(
            start,
            end,
            campaign_sha256="a" * 64,
            machine_fingerprint_sha256="b" * 64,
            covered_experiment_ids=["mx-01"],
            planned_experiments=24,
            operator_note="x" * 4097,
        )
