from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "benchmark" / "capture_machine_profile.py"
SPEC = importlib.util.spec_from_file_location("morpheus_capture_machine_profile", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _profile(timestamp: str, commit: str, temp: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "protocol": "morpheus-machine-profile-v2",
        "captured_at": timestamp,
        "source_commit": commit,
        "platform": {"system": "Linux", "machine": "x86_64", "python": "3.14"},
        "cpu": {"logical_count": 16, "linux": {"model_name": "Example CPU", "flags": ["sse2"]}, "windows": {}},
        "toolchain": {"compiler": "/usr/bin/g++", "compiler_version": "GCC 15", "cmake": "cmake 4", "git": "git 2"},
        "environment": {"python_executable": "/usr/bin/python", "temp": temp},
    }


def test_fingerprint_ignores_capture_time_commit_and_temp_path() -> None:
    first = _profile("2026-08-28T00:00:00Z", "a" * 40, "/tmp/a")
    second = _profile("2026-08-29T00:00:00Z", "b" * 40, "/tmp/b")
    assert module.machine_profile_fingerprint(first) == module.machine_profile_fingerprint(second)


def test_fingerprint_changes_when_machine_or_toolchain_identity_changes() -> None:
    first = _profile("2026-08-28T00:00:00Z", "a" * 40, "/tmp/a")
    second = _profile("2026-08-28T00:00:00Z", "a" * 40, "/tmp/a")
    second["cpu"]["logical_count"] = 32  # type: ignore[index]
    assert module.machine_profile_fingerprint(first) != module.machine_profile_fingerprint(second)


def test_machine_identity_document_excludes_run_provenance() -> None:
    profile = _profile("2026-08-28T00:00:00Z", "a" * 40, "/tmp/a")
    identity = module.machine_identity_document(profile)
    assert "captured_at" not in identity
    assert "source_commit" not in identity
    assert "environment" not in identity
    assert identity["platform"] == profile["platform"]
