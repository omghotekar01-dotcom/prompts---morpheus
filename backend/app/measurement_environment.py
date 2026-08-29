from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import platform
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


SNAPSHOT_SCHEMA = "morpheus-measurement-environment-snapshot-v1"
RECORD_SCHEMA = "morpheus-measurement-environment-record-v1"
SNAPSHOT_EVIDENCE_STATE = "OBSERVED_MEASUREMENT_ENVIRONMENT_METADATA_NOT_CONTROL_PROOF"
LOCAL_RECORD_EVIDENCE_STATE = "LOCAL_MEASUREMENT_ENVIRONMENT_METADATA_CAPTURED_NOT_CONTROL_PROOF"
CI_RECORD_EVIDENCE_STATE = "CI_MEASUREMENT_ENVIRONMENT_METADATA_NOT_PUBLICATION_CONTROL"

_SNAPSHOT_TRUTH_BOUNDARY = (
    "This snapshot records observable process/OS measurement conditions only. It does not prove exclusive machine access, "
    "stable clock frequency, absence of interrupts, cache state, NUMA placement, or thermal equilibrium."
)
_RECORD_TRUTH_BOUNDARIES = [
    "Start/end environment observations are provenance metadata, not a proof that conditions remained constant between captures.",
    "Coverage names only experiments newly measured during this invocation; reused resume cells are intentionally excluded.",
    "A stable affinity/power/governor observation does not establish exclusive machine access or eliminate scheduler, interrupt, thermal, cache or NUMA effects.",
    "GitHub Actions environment records remain CI metadata and cannot upgrade CI timing into publication measurements.",
]


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value != "0" * 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _finite_number(value: Any, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("measurement environment numeric value must be an integer or float")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("measurement environment numeric value must be finite")
    if minimum is not None and numeric < minimum:
        raise ValueError(f"measurement environment numeric value must be >= {minimum}")
    return numeric


def _parse_timestamp(value: Any, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be a canonical ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset")
    return parsed


def _canonical_experiment_id(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("covered experiment ids must be canonical non-empty strings")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("covered experiment ids cannot contain control characters")
    return value


def _command_line(command: list[str], timeout: int = 5) -> str | None:
    try:
        process = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (process.stdout or process.stderr).strip()
    return text if process.returncode == 0 and text else None


def _process_affinity() -> list[int] | None:
    if hasattr(os, "sched_getaffinity"):
        try:
            return sorted(int(cpu) for cpu in os.sched_getaffinity(0))
        except OSError:
            return None
    if platform.system() == "Windows":
        raw = _command_line(
            ["powershell", "-NoProfile", "-Command", f"(Get-Process -Id {os.getpid()}).ProcessorAffinity"]
        )
        if raw:
            try:
                mask = int(raw.splitlines()[-1].strip())
            except ValueError:
                return None
            return [index for index in range(max(1, os.cpu_count() or 1)) if mask & (1 << index)]
    return None


def _linux_governors() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_path in sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor")):
        path = Path(raw_path)
        try:
            values[path.parts[-3]] = path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            continue
    return values


def _linux_frequency_summary() -> dict[str, float | int] | None:
    values: list[int] = []
    for raw_path in sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq")):
        try:
            value = int(Path(raw_path).read_text(encoding="utf-8", errors="ignore").strip())
        except (OSError, ValueError):
            continue
        if value > 0:
            values.append(value)
    if not values:
        return None
    return {
        "observed_cpu_count": len(values),
        "min_khz": min(values),
        "mean_khz": sum(values) / len(values),
        "max_khz": max(values),
    }


def _thermal_summary() -> dict[str, float | int] | None:
    values: list[float] = []
    for raw_path in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
        try:
            raw = float(Path(raw_path).read_text(encoding="utf-8", errors="ignore").strip())
        except (OSError, ValueError):
            continue
        celsius = raw / 1000.0 if abs(raw) > 1000 else raw
        if math.isfinite(celsius) and -50.0 <= celsius <= 200.0:
            values.append(celsius)
    if not values:
        return None
    return {
        "sensor_count": len(values),
        "min_celsius": min(values),
        "mean_celsius": sum(values) / len(values),
        "max_celsius": max(values),
    }


def _windows_power_scheme() -> str | None:
    if platform.system() != "Windows":
        return None
    raw = _command_line(["powercfg", "/getactivescheme"])
    return re.sub(r"\s+", " ", raw).strip() if raw else None


def _load_average() -> dict[str, float] | None:
    try:
        one, five, fifteen = os.getloadavg()
    except (AttributeError, OSError):
        return None
    cpus = max(1, os.cpu_count() or 1)
    return {
        "one_minute": float(one),
        "five_minutes": float(five),
        "fifteen_minutes": float(fifteen),
        "one_minute_per_logical_cpu": float(one) / cpus,
    }


def capture_measurement_environment_snapshot() -> dict[str, Any]:
    core: dict[str, Any] = {
        "schema": SNAPSHOT_SCHEMA,
        "captured_at": datetime.now(UTC).isoformat(),
        "platform": platform.system(),
        "logical_cpu_count": os.cpu_count(),
        "process_affinity": _process_affinity(),
        "load_average": _load_average(),
        "linux_scaling_governors": _linux_governors(),
        "linux_frequency_summary": _linux_frequency_summary(),
        "windows_active_power_scheme": _windows_power_scheme(),
        "thermal_summary": _thermal_summary(),
        "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
        "evidence_state": SNAPSHOT_EVIDENCE_STATE,
        "truth_boundary": _SNAPSHOT_TRUTH_BOUNDARY,
    }
    return {**core, "snapshot_sha256": _canonical_sha256(core)}


def _validate_load_average(value: Any, logical_cpu_count: int) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping) or set(value) != {
        "one_minute",
        "five_minutes",
        "fifteen_minutes",
        "one_minute_per_logical_cpu",
    }:
        raise ValueError("measurement-environment load_average has unexpected schema")
    one = _finite_number(value["one_minute"], minimum=0.0)
    _finite_number(value["five_minutes"], minimum=0.0)
    _finite_number(value["fifteen_minutes"], minimum=0.0)
    normalized = _finite_number(value["one_minute_per_logical_cpu"], minimum=0.0)
    if not math.isclose(normalized, one / logical_cpu_count, rel_tol=1e-9, abs_tol=1e-12):
        raise ValueError("measurement-environment normalized load does not match logical CPU count")


def _validate_frequency_summary(value: Any, logical_cpu_count: int) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping) or set(value) != {"observed_cpu_count", "min_khz", "mean_khz", "max_khz"}:
        raise ValueError("measurement-environment frequency summary has unexpected schema")
    observed = value["observed_cpu_count"]
    if isinstance(observed, bool) or not isinstance(observed, int) or not 1 <= observed <= logical_cpu_count:
        raise ValueError("measurement-environment observed frequency CPU count is invalid")
    minimum = _finite_number(value["min_khz"], minimum=0.000001)
    mean = _finite_number(value["mean_khz"], minimum=0.000001)
    maximum = _finite_number(value["max_khz"], minimum=0.000001)
    if not minimum <= mean <= maximum:
        raise ValueError("measurement-environment frequency summary ordering is invalid")


def _validate_thermal_summary(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping) or set(value) != {"sensor_count", "min_celsius", "mean_celsius", "max_celsius"}:
        raise ValueError("measurement-environment thermal summary has unexpected schema")
    sensor_count = value["sensor_count"]
    if isinstance(sensor_count, bool) or not isinstance(sensor_count, int) or sensor_count <= 0:
        raise ValueError("measurement-environment thermal sensor count is invalid")
    minimum = _finite_number(value["min_celsius"])
    mean = _finite_number(value["mean_celsius"])
    maximum = _finite_number(value["max_celsius"])
    if not -50.0 <= minimum <= mean <= maximum <= 200.0:
        raise ValueError("measurement-environment thermal summary is outside the accepted physical range")


def _validate_snapshot(snapshot: Mapping[str, Any]) -> datetime:
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("unexpected measurement-environment snapshot schema")
    sha = snapshot.get("snapshot_sha256")
    if not _valid_sha256(sha):
        raise ValueError("measurement-environment snapshot lacks a non-placeholder SHA-256 identity")
    core = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    if _canonical_sha256(core) != sha:
        raise ValueError("measurement-environment snapshot hash mismatch")
    captured_at = _parse_timestamp(snapshot.get("captured_at"), name="measurement-environment captured_at")
    system = snapshot.get("platform")
    if not isinstance(system, str) or not system.strip() or system != system.strip():
        raise ValueError("measurement-environment platform must be a canonical non-empty string")
    logical_cpu_count = snapshot.get("logical_cpu_count")
    if isinstance(logical_cpu_count, bool) or not isinstance(logical_cpu_count, int) or logical_cpu_count <= 0:
        raise ValueError("measurement-environment logical_cpu_count must be positive")
    affinity = snapshot.get("process_affinity")
    if affinity is not None:
        if (
            not isinstance(affinity, list)
            or not affinity
            or any(isinstance(cpu, bool) or not isinstance(cpu, int) or cpu < 0 or cpu >= logical_cpu_count for cpu in affinity)
            or len(set(affinity)) != len(affinity)
            or affinity != sorted(affinity)
        ):
            raise ValueError("measurement-environment process_affinity must be a sorted unique in-range CPU list")
    _validate_load_average(snapshot.get("load_average"), logical_cpu_count)
    governors = snapshot.get("linux_scaling_governors")
    if not isinstance(governors, Mapping):
        raise ValueError("measurement-environment linux_scaling_governors must be an object")
    for cpu, governor in governors.items():
        if not isinstance(cpu, str) or not cpu or not isinstance(governor, str) or not governor.strip():
            raise ValueError("measurement-environment governor entries must be canonical non-empty strings")
    _validate_frequency_summary(snapshot.get("linux_frequency_summary"), logical_cpu_count)
    power = snapshot.get("windows_active_power_scheme")
    if power is not None and (not isinstance(power, str) or not power.strip() or power != power.strip()):
        raise ValueError("measurement-environment Windows power scheme must be a canonical non-empty string")
    _validate_thermal_summary(snapshot.get("thermal_summary"))
    if not isinstance(snapshot.get("github_actions"), bool):
        raise ValueError("measurement-environment github_actions must be boolean")
    if snapshot.get("evidence_state") != SNAPSHOT_EVIDENCE_STATE:
        raise ValueError("measurement-environment snapshot evidence_state is invalid")
    if snapshot.get("truth_boundary") != _SNAPSHOT_TRUTH_BOUNDARY:
        raise ValueError("measurement-environment snapshot truth boundary is invalid")
    return captured_at


def _expected_stability(start: Mapping[str, Any], end: Mapping[str, Any]) -> dict[str, bool]:
    start_affinity = start.get("process_affinity")
    end_affinity = end.get("process_affinity")
    return {
        "process_affinity_stable": start_affinity is not None and start_affinity == end_affinity,
        "linux_governors_stable": (
            start.get("linux_scaling_governors") == end.get("linux_scaling_governors")
            and bool(start.get("linux_scaling_governors"))
        ),
        "windows_power_scheme_stable": (
            start.get("windows_active_power_scheme") is not None
            and start.get("windows_active_power_scheme") == end.get("windows_active_power_scheme")
        ),
        "same_logical_cpu_count": start.get("logical_cpu_count") == end.get("logical_cpu_count"),
    }


def build_measurement_environment_record(
    start: Mapping[str, Any],
    end: Mapping[str, Any],
    *,
    campaign_sha256: str,
    machine_fingerprint_sha256: str,
    covered_experiment_ids: Sequence[str],
    planned_experiments: int,
    resumed_from_campaign_sha256: str | None = None,
    operator_note: str | None = None,
) -> dict[str, Any]:
    start_time = _validate_snapshot(start)
    end_time = _validate_snapshot(end)
    if not _valid_sha256(campaign_sha256):
        raise ValueError("campaign_sha256 must be a non-placeholder lowercase SHA-256 identity")
    if not _valid_sha256(machine_fingerprint_sha256):
        raise ValueError("machine_fingerprint_sha256 must be a non-placeholder lowercase SHA-256 identity")
    if resumed_from_campaign_sha256 is not None and not _valid_sha256(resumed_from_campaign_sha256):
        raise ValueError("resumed_from_campaign_sha256 must be a non-placeholder lowercase SHA-256 identity")
    if start.get("platform") != end.get("platform"):
        raise ValueError("measurement environment platform changed during campaign")
    if start.get("github_actions") != end.get("github_actions"):
        raise ValueError("measurement environment CI identity changed during campaign")
    if end_time < start_time:
        raise ValueError("measurement environment end snapshot predates start snapshot")
    if isinstance(planned_experiments, bool) or not isinstance(planned_experiments, int) or planned_experiments <= 0:
        raise ValueError("planned_experiments must be positive")
    coverage = [_canonical_experiment_id(item) for item in covered_experiment_ids]
    if not coverage or len(set(coverage)) != len(coverage):
        raise ValueError("covered_experiment_ids must be unique and non-empty")
    if len(coverage) > planned_experiments:
        raise ValueError("environment coverage cannot exceed planned experiment count")
    if operator_note is not None:
        if not isinstance(operator_note, str):
            raise ValueError("operator_note must be a string")
        normalized_note = operator_note.strip()
        if len(normalized_note) > 4096:
            raise ValueError("operator_note exceeds 4096 characters")
    else:
        normalized_note = ""

    ci = start.get("github_actions") is True
    complete_coverage = len(coverage) == planned_experiments and resumed_from_campaign_sha256 is None
    core = {
        "schema": RECORD_SCHEMA,
        "campaign_sha256": campaign_sha256,
        "machine_fingerprint_sha256": machine_fingerprint_sha256,
        "start_snapshot": dict(start),
        "end_snapshot": dict(end),
        "coverage": {
            "covered_experiment_ids": coverage,
            "covered_experiment_count": len(coverage),
            "planned_experiments": planned_experiments,
            "complete_single_invocation_coverage": complete_coverage,
            "resumed_from_campaign_sha256": resumed_from_campaign_sha256,
        },
        "observed_stability": _expected_stability(start, end),
        "operator_note": normalized_note or None,
        "evidence_state": CI_RECORD_EVIDENCE_STATE if ci else LOCAL_RECORD_EVIDENCE_STATE,
        "truth_boundaries": list(_RECORD_TRUTH_BOUNDARIES),
    }
    return {**core, "record_sha256": _canonical_sha256(core)}


def validate_measurement_environment_record(payload: Mapping[str, Any]) -> None:
    if payload.get("schema") != RECORD_SCHEMA:
        raise ValueError("unexpected measurement-environment record schema")
    for field in ("campaign_sha256", "machine_fingerprint_sha256", "record_sha256"):
        if not _valid_sha256(payload.get(field)):
            raise ValueError(f"measurement-environment record has invalid or placeholder {field}")
    start = payload.get("start_snapshot")
    end = payload.get("end_snapshot")
    coverage = payload.get("coverage")
    if not isinstance(start, Mapping) or not isinstance(end, Mapping):
        raise ValueError("measurement-environment record requires start/end snapshots")
    if not isinstance(coverage, Mapping):
        raise ValueError("measurement-environment record requires explicit experiment coverage")
    start_time = _validate_snapshot(start)
    end_time = _validate_snapshot(end)
    if start.get("platform") != end.get("platform"):
        raise ValueError("measurement-environment record platform mismatch")
    if start.get("github_actions") != end.get("github_actions"):
        raise ValueError("measurement-environment record CI identity changed between snapshots")
    if end_time < start_time:
        raise ValueError("measurement-environment record end snapshot predates start snapshot")

    ids = coverage.get("covered_experiment_ids")
    count = coverage.get("covered_experiment_count")
    planned = coverage.get("planned_experiments")
    resumed = coverage.get("resumed_from_campaign_sha256")
    if not isinstance(ids, list) or not ids:
        raise ValueError("measurement-environment record has invalid experiment coverage ids")
    try:
        canonical_ids = [_canonical_experiment_id(item) for item in ids]
    except ValueError as exc:
        raise ValueError("measurement-environment record has invalid experiment coverage ids") from exc
    if len(set(canonical_ids)) != len(canonical_ids):
        raise ValueError("measurement-environment record experiment coverage ids must be unique")
    if count != len(canonical_ids) or isinstance(planned, bool) or not isinstance(planned, int) or planned <= 0 or len(canonical_ids) > planned:
        raise ValueError("measurement-environment record coverage counts are inconsistent")
    if resumed is not None and not _valid_sha256(resumed):
        raise ValueError("measurement-environment record has invalid resume identity")
    expected_complete = len(canonical_ids) == planned and resumed is None
    if coverage.get("complete_single_invocation_coverage") is not expected_complete:
        raise ValueError("measurement-environment record complete coverage flag is inconsistent")

    observed_stability = payload.get("observed_stability")
    expected_stability = _expected_stability(start, end)
    if not isinstance(observed_stability, Mapping) or dict(observed_stability) != expected_stability:
        raise ValueError("measurement-environment observed stability does not match start/end snapshots")

    operator_note = payload.get("operator_note")
    if operator_note is not None and (
        not isinstance(operator_note, str)
        or not operator_note
        or operator_note != operator_note.strip()
        or len(operator_note) > 4096
    ):
        raise ValueError("measurement-environment operator_note is invalid")

    expected_state = CI_RECORD_EVIDENCE_STATE if start.get("github_actions") is True else LOCAL_RECORD_EVIDENCE_STATE
    if payload.get("evidence_state") != expected_state:
        raise ValueError("measurement-environment record evidence_state is inconsistent with snapshots")
    if payload.get("truth_boundaries") != _RECORD_TRUTH_BOUNDARIES:
        raise ValueError("measurement-environment record truth boundaries are invalid")
    core = {key: value for key, value in payload.items() if key != "record_sha256"}
    if _canonical_sha256(core) != payload.get("record_sha256"):
        raise ValueError("measurement-environment record hash mismatch")
