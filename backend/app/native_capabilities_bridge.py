from __future__ import annotations

"""Thin protocol adapter for compiled C++20 DSA capability filtering.

The executable owns the compatibility decision in native mode. Python formats
validated typed inputs and verifies a complete output, not eligibility rules.
"""

from functools import lru_cache
import os
from pathlib import Path
import shutil
import subprocess

from .models import QuerySpec, WorkloadSpec


class NativeCapabilityError(RuntimeError):
    pass


def capability_executable() -> Path | None:
    override = os.getenv("MORPHEUS_CAPABILITY_EXECUTABLE")
    suffix = ".exe" if os.name == "nt" else ""
    root = Path(__file__).resolve().parents[2]
    choices = ([Path(override)] if override else [
        root / "bin" / "windows-x64" / ("morpheus_native_capabilities" + suffix),
        root / "build" / "core" / ("morpheus_native_capabilities" + suffix),
        root / "build" / "core" / "Release" / ("morpheus_native_capabilities" + suffix),
    ])
    for path in choices:
        if path.is_file():
            return path
    if not override:
        which = shutil.which("morpheus_native_capabilities")
        if which:
            return Path(which)
    return None


@lru_cache(maxsize=4096)
def _request(executable: str, record_count: int, operation: str,
             field_type: str, cardinality: int) -> dict[str, str]:
    # Every query is evaluated by C++ from the declared operation/schema.
    safe_type = "_".join(field_type.lower().split()) or "-"
    payload = f"MORPHEUS_CAPABILITIES_V1\n{record_count} 1\n{operation} {safe_type} {cardinality}\n"
    try:
        process = subprocess.run([executable], input=payload, text=True, capture_output=True,
                                 timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeCapabilityError(f"Native capability engine unavailable: {exc}") from exc
    if process.returncode:
        raise NativeCapabilityError("Native C++ capability engine refused input: " + process.stderr[:350])
    lines = process.stdout.splitlines()
    if not lines or lines[0] != "OK 1 6" or len(lines) != 7:
        raise NativeCapabilityError("Invalid or truncated native C++ capability response")
    expected = {"robin_hood_hash", "sorted_array", "ordered_tree",
                "radix_trie", "bitmap", "csr_graph"}
    accepted = {"eligible", "unsupported_operation", "incompatible_type", "excessive_cardinality"}
    result: dict[str, str] = {}
    for line in lines[1:]:
        row = line.split()
        if len(row) != 4 or row[0] != "R" or row[1] != "0" or row[3] not in accepted:
            raise NativeCapabilityError("Malformed native capability verdict")
        if row[2] in result or row[2] not in expected:
            raise NativeCapabilityError("Unexpected or duplicated native capability primitive")
        result[row[2]] = row[3]
    if set(result) != expected:
        raise NativeCapabilityError("Native capability registry and API contract do not match")
    return result


def native_capability_result(spec: WorkloadSpec, query: QuerySpec) -> dict[str, str] | None:
    mode = os.getenv("MORPHEUS_CAPABILITY_BACKEND", "auto").strip().lower()
    if mode not in {"auto", "native", "python"}:
        raise NativeCapabilityError("MORPHEUS_CAPABILITY_BACKEND must be auto, native or python")
    if mode == "python":
        return None
    executable = capability_executable()
    if executable is None:
        if mode == "native":
            raise NativeCapabilityError("Required C++20 capability engine is missing")
        return None
    field = next((x for x in spec.fields if x.name == query.field), None)
    return _request(str(executable), spec.record_count, query.kind.value,
                    field.type if field else "", int(field.cardinality or 0) if field else 0)
