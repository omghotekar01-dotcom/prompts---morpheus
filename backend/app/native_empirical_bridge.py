from __future__ import annotations

"""Transport for opt-in C++20 learned cost predictions from operator measurements.

This adapter does not fit coefficients, choose candidates, or synthesize sample data.
No matching model means NO LEARNED EVIDENCE, not a fabricated prediction.
"""

from functools import lru_cache
import hashlib
import math
import os
from pathlib import Path
import subprocess


class NativeEmpiricalError(RuntimeError):
    pass


@lru_cache(maxsize=4096)
def _invoke(executable: str, filename: str, timestamp_ns: int, primitive: str,
            operation: str, records: int, cardinality: int,
            selectivity: float, updates: float) -> tuple[float, float, int, str] | None:
    del timestamp_ns  # included in the cache key to invalidate changed benchmark inputs
    evidence = Path(filename)
    if evidence.stat().st_size > 4_000_000:
        raise NativeEmpiricalError("Native empirical evidence exceeds 4 MB")
    raw = evidence.read_text(encoding="utf-8")
    lines = raw.splitlines()
    if len(lines) < 3 or lines[0].strip() != "MORPHEUS_EMPIRICAL_COST_V1":
        raise NativeEmpiricalError("Invalid native empirical training file protocol")
    try:
        count = int(lines[1].strip())
    except ValueError as exc:
        raise NativeEmpiricalError("Invalid native empirical sample count") from exc
    if not 1 <= count <= 100_000 or len(lines) != count + 2:
        raise NativeEmpiricalError("Native empirical training sample count mismatch")
    payload = (raw.rstrip("\n") +
               f"\n1\n{primitive} {operation} {records} {cardinality} {selectivity:.17g} {updates:.17g}\n")
    try:
        result = subprocess.run([executable], input=payload, text=True, capture_output=True,
                                check=False, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeEmpiricalError(f"C++ empirical estimator not available: {exc}") from exc
    if result.returncode:
        raise NativeEmpiricalError("C++ empirical estimator rejected evidence: " + result.stderr[:400])
    response = result.stdout.splitlines()
    if len(response) != 2 or response[0] != "OK 1":
        raise NativeEmpiricalError("Invalid C++ empirical output header")
    if response[1].startswith("U "):
        return None
    result_row = response[1].split()
    if len(result_row) != 4 or result_row[0] != "P":
        raise NativeEmpiricalError("Invalid C++ empirical prediction row")
    try:
        value, rmse, observations = float(result_row[1]), float(result_row[2]), int(result_row[3])
    except ValueError as exc:
        raise NativeEmpiricalError("Invalid C++ empirical numerical prediction") from exc
    if (not math.isfinite(value) or value <= 0 or
        not math.isfinite(rmse) or rmse < 0 or observations < 8):
        raise NativeEmpiricalError("Invalid or unsupported C++ empirical prediction")
    return value, rmse, observations, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def native_empirical_latency(primitive: str, operation: str, records: int,
                             cardinality: int, selectivity: float,
                             updates_per_second: float) -> tuple[float, float, int, str] | None:
    filename = os.getenv("MORPHEUS_EMPIRICAL_COST_TRAINING_FILE", "").strip()
    if not filename:
        return None
    executable = os.getenv("MORPHEUS_EMPIRICAL_COST_EXECUTABLE", "").strip()
    if not executable or not Path(executable).is_file():
        raise NativeEmpiricalError("Native empirical training was enabled without a C++20 executable")
    evidence = Path(filename)
    if not evidence.is_file():
        raise NativeEmpiricalError("Native empirical training file not found")
    if not primitive or not operation or any(c.isspace() for c in primitive + operation):
        raise NativeEmpiricalError("Invalid native empirical identity")
    return _invoke(executable, filename, evidence.stat().st_mtime_ns, primitive, operation,
                   records, cardinality, selectivity, updates_per_second)
