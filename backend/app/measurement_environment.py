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


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


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
        "evidence_state": "OBSERVED_MEASUREMENT_ENVIRONMENT_METADATA_NOT_CONTROL_PROOF",
        "truth_boundary": (
            "This snapshot records observable process/OS measurement conditions only. It does not prove exclusive machine access, "
            "stable clock frequency, absence of interrupts, cache state, NUMA placement, or thermal equilibrium."
        ),
    }
    return {**core, "snapshot_sha256": _canonical_sha256(core)}


def _validate_snapshot(snapshot: Mapping[str, Any]) -> None:
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("unexpected measurement-environment snapshot schema")
    sha = snapshot.get("snapshot_sha256")
    if not isinstance(sha, str) or len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise ValueError("measurement-environment snapshot lacks SHA-256 identity")
    core = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    if _canonical_sha256(core) != sha:
        raise ValueError("measurement-environment snapshot hash mismatch")


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
    _validate_snapshot(start)
    _validate_snapshot(end)
    for name, value in (("campaign_sha256", campaign_sha256), ("machine_fingerprint_sha256", machine_fingerprint_sha256)):
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError(f"{name} must be a lowercase SHA-256 identity")
    if resumed_from_campaign_sha256 is not None and (
        len(resumed_from_campaign_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in resumed_from_campaign_sha256)
    ):
        raise ValueError("resumed_from_campaign_sha256 must be a lowercase SHA-256 identity")
    if start.get("platform") != end.get("platform"):
        raise ValueError("measurement environment platform changed during campaign")
    if isinstance(planned_experiments, bool) or not isinstance(planned_experiments, int) or planned_experiments <= 0:
        raise ValueError("planned_experiments must be positive")
    coverage = [str(item).strip() for item in covered_experiment_ids]
    if not coverage or any(not item for item in coverage) or len(set(coverage)) != len(coverage):
        raise ValueError("covered_experiment_ids must be unique and non-empty")
    if len(coverage) > planned_experiments:
        raise ValueError("environment coverage cannot exceed planned experiment count")

    start_affinity = start.get("process_affinity")
    end_affinity = end.get("process_affinity")
    affinity_stable = start_affinity is not None and start_affinity == end_affinity
    governors_stable = start.get("linux_scaling_governors") == end.get("linux_scaling_governors") and bool(start.get("linux_scaling_governors"))
    power_stable = start.get("windows_active_power_scheme") is not None and start.get("windows_active_power_scheme") == end.get("windows_active_power_scheme")
    ci = start.get("github_actions") is True or end.get("github_actions") is True
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
        "observed_stability": {
            "process_affinity_stable": affinity_stable,
            "linux_governors_stable": governors_stable,
            "windows_power_scheme_stable": power_stable,
            "same_logical_cpu_count": start.get("logical_cpu_count") == end.get("logical_cpu_count"),
        },
        "operator_note": operator_note.strip() if operator_note and operator_note.strip() else None,
        "evidence_state": (
            "CI_MEASUREMENT_ENVIRONMENT_METADATA_NOT_PUBLICATION_CONTROL"
            if ci
            else "LOCAL_MEASUREMENT_ENVIRONMENT_METADATA_CAPTURED_NOT_CONTROL_PROOF"
        ),
        "truth_boundaries": [
            "Start/end environment observations are provenance metadata, not a proof that conditions remained constant between captures.",
            "Coverage names only experiments newly measured during this invocation; reused resume cells are intentionally excluded.",
            "A stable affinity/power/governor observation does not establish exclusive machine access or eliminate scheduler, interrupt, thermal, cache or NUMA effects.",
            "GitHub Actions environment records remain CI metadata and cannot upgrade CI timing into publication measurements.",
        ],
    }
    return {**core, "record_sha256": _canonical_sha256(core)}


def validate_measurement_environment_record(payload: Mapping[str, Any]) -> None:
    if payload.get("schema") != RECORD_SCHEMA:
        raise ValueError("unexpected measurement-environment record schema")
    for field in ("campaign_sha256", "machine_fingerprint_sha256", "record_sha256"):
        value = payload.get(field)
        if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError(f"measurement-environment record has invalid {field}")
    start = payload.get("start_snapshot")
    end = payload.get("end_snapshot")
    coverage = payload.get("coverage")
    if not isinstance(start, Mapping) or not isinstance(end, Mapping):
        raise ValueError("measurement-environment record requires start/end snapshots")
    if not isinstance(coverage, Mapping):
        raise ValueError("measurement-environment record requires explicit experiment coverage")
    _validate_snapshot(start)
    _validate_snapshot(end)
    if start.get("platform") != end.get("platform"):
        raise ValueError("measurement-environment record platform mismatch")
    ids = coverage.get("covered_experiment_ids")
    count = coverage.get("covered_experiment_count")
    planned = coverage.get("planned_experiments")
    resumed = coverage.get("resumed_from_campaign_sha256")
    if not isinstance(ids, list) or not ids or any(not isinstance(item, str) or not item for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("measurement-environment record has invalid experiment coverage ids")
    if count != len(ids) or isinstance(planned, bool) or not isinstance(planned, int) or planned <= 0 or len(ids) > planned:
        raise ValueError("measurement-environment record coverage counts are inconsistent")
    if resumed is not None and (not isinstance(resumed, str) or len(resumed) != 64 or any(ch not in "0123456789abcdef" for ch in resumed)):
        raise ValueError("measurement-environment record has invalid resume identity")
    expected_complete = len(ids) == planned and resumed is None
    if coverage.get("complete_single_invocation_coverage") is not expected_complete:
        raise ValueError("measurement-environment record complete coverage flag is inconsistent")
    expected_state = (
        "CI_MEASUREMENT_ENVIRONMENT_METADATA_NOT_PUBLICATION_CONTROL"
        if start.get("github_actions") is True or end.get("github_actions") is True
        else "LOCAL_MEASUREMENT_ENVIRONMENT_METADATA_CAPTURED_NOT_CONTROL_PROOF"
    )
    if payload.get("evidence_state") != expected_state:
        raise ValueError("measurement-environment record evidence_state is inconsistent with snapshots")
    core = {key: value for key, value in payload.items() if key != "record_sha256"}
    if _canonical_sha256(core) != payload.get("record_sha256"):
        raise ValueError("measurement-environment record hash mismatch")
