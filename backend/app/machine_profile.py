from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MACHINE_PROFILE_PROTOCOL = "morpheus-machine-profile-v2"


def _command_first_line(command: list[str]) -> str | None:
    try:
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=6,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (process.stdout or process.stderr).splitlines()
    return lines[0].strip() if process.returncode == 0 and lines else None


def _git_commit() -> str | None:
    try:
        process = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = process.stdout.strip()
    return value if process.returncode == 0 and value else None


def _linux_cpu_metadata() -> dict[str, Any]:
    path = Path("/proc/cpuinfo")
    if not path.is_file():
        return {}
    model_name = None
    flags: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        if key == "model name" and model_name is None:
            model_name = value
        elif key in {"flags", "Features"} and not flags:
            flags = value.split()
    return {"model_name": model_name, "flags": flags[:128]}


def _windows_cpu_metadata() -> dict[str, Any]:
    if platform.system() != "Windows":
        return {}
    try:
        process = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json -Compress",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if process.returncode != 0 or not process.stdout.strip():
        return {}
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError:
        return {}


def machine_identity_document(profile: dict[str, Any]) -> dict[str, Any]:
    """Return stable machine/toolchain identity fields, excluding run metadata."""

    return {
        "schema_version": profile.get("schema_version"),
        "protocol": profile.get("protocol"),
        "platform": profile.get("platform"),
        "cpu": profile.get("cpu"),
        "toolchain": profile.get("toolchain"),
    }


def machine_profile_fingerprint(profile: dict[str, Any]) -> str:
    canonical = json.dumps(
        machine_identity_document(profile),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def capture_machine_profile() -> dict[str, Any]:
    compiler = shutil.which("g++") or shutil.which("clang++") or shutil.which("cl")
    compiler_version = (
        _command_first_line([compiler, "--version"])
        if compiler and not compiler.lower().endswith("cl.exe")
        else None
    )
    if compiler and compiler.lower().endswith("cl.exe"):
        compiler_version = _command_first_line([compiler])

    profile: dict[str, Any] = {
        "schema_version": 2,
        "protocol": MACHINE_PROFILE_PROTOCOL,
        "captured_at": datetime.now(UTC).isoformat(),
        "source_commit": _git_commit(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "cpu": {
            "logical_count": os.cpu_count(),
            "linux": _linux_cpu_metadata(),
            "windows": _windows_cpu_metadata(),
        },
        "toolchain": {
            "compiler": compiler,
            "compiler_version": compiler_version,
            "cmake": _command_first_line(["cmake", "--version"]) if shutil.which("cmake") else None,
            "git": _command_first_line(["git", "--version"]) if shutil.which("git") else None,
        },
        "environment": {
            "python_executable": os.path.realpath(os.sys.executable),
            "temp": os.environ.get("TEMP") or os.environ.get("TMP") or os.environ.get("TMPDIR"),
        },
        "truth_note": (
            "This profile captures readily observable machine/toolchain metadata only. Frequency governor, "
            "cache topology, thermals, background load and affinity require additional controlled measurement."
        ),
    }
    profile["machine_fingerprint_sha256"] = machine_profile_fingerprint(profile)
    profile["machine_identity"] = machine_identity_document(profile)
    return profile


# Backward-compatible name used by older benchmark code.
def capture() -> dict[str, Any]:
    return capture_machine_profile()
