from __future__ import annotations

"""Native C++20 inspection of actual submitted CSV bytes; not example data."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]


class CsvProfilingError(ValueError):
    pass


class CsvProfilerMissing(RuntimeError):
    pass


def _profiler_executable() -> Path:
    configured = os.getenv("MORPHEUS_CSV_PROFILE_EXECUTABLE")
    suffix = ".exe" if os.name == "nt" else ""
    candidates = ([Path(configured)] if configured else [
        _ROOT / "bin" / ("morpheus_csv_profile" + suffix),
        _ROOT / "build" / "core" / ("morpheus_csv_profile" + suffix),
        _ROOT / "build" / "core" / "Release" / ("morpheus_csv_profile" + suffix),
    ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    if not configured:
        located = shutil.which("morpheus_csv_profile")
        if located:
            return Path(located)
    raise CsvProfilerMissing("C++ CSV profiler is not installed; build morpheus_csv_profile")


def profile_submitted_csv(csv_text: str) -> dict[str, Any]:
    if not csv_text or len(csv_text.encode("utf-8")) > 15_000_000:
        raise CsvProfilingError("CSV must contain 1 to 15,000,000 UTF-8 bytes")
    executable = _profiler_executable()
    try:
        completed = subprocess.run(
            [str(executable)],
            input=csv_text,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CsvProfilerMissing(f"C++ CSV profiler execution failed: {exc}") from exc
    if completed.returncode:
        raise CsvProfilingError(
            "C++ profiler rejected the submitted CSV: " + completed.stderr.strip()[:300]
        )
    lines = completed.stdout.splitlines()
    if not lines:
        raise CsvProfilingError("empty native CSV profiling result")
    header = lines[0].split()
    if len(header) != 3 or header[0] != "PROFILE_V1":
        raise CsvProfilingError("invalid native CSV profiler result header")
    try:
        rows, nfields = int(header[1]), int(header[2])
    except ValueError as exc:
        raise CsvProfilingError("malformed CSV profile counts") from exc
    if not (1 <= rows <= 100000 and 1 <= nfields <= 64 and len(lines) == nfields + 1):
        raise CsvProfilingError("inconsistent native CSV profile dimensions")
    fields = []
    names = set()
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != 4 or parts[0] != "FIELD":
            raise CsvProfilingError("invalid CSV field profile")
        _, name, kind, count_raw = parts
        try:
            count = int(count_raw)
        except ValueError as exc:
            raise CsvProfilingError("invalid distinct value count") from exc
        if (name in names or kind not in {"int", "uint64", "double", "string"}
                or not 1 <= count <= rows):
            raise CsvProfilingError("invalid native CSV profile column")
        names.add(name)
        fields.append({"name": name, "type": kind, "cardinality": count})
    return {
        "record_count": rows,
        "fields": fields,
        "provenance": "EXACT_SUBMITTED_CSV_CONTENTS_NATIVE_CPP20",
        "performance_evidence": "NOT_BENCHMARKED",
    }
