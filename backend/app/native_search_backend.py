from __future__ import annotations

"""Bounded API-to-native bridge for the C++20 MORPHEUS search algorithm.

Python validates the workload, resolves per-primitive cost-model inputs and
adapts the result to the existing API models. The combinatorial search,
candidate exploration and beam/greedy decisions run in compiled C++.
This bridge never executes a shell or user-provided command string.
"""

import os
import shutil
import subprocess
from pathlib import Path

from .calibration import CALIBRATIONS
from .catalog import PRIMITIVES
from .cost_model import estimate_query_latency_us
from .index_footprint import predicted_index_bytes
from .models import QueryKind, SearchStrategy, WorkloadSpec


_MUTATIONS = {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}
_ROOT = Path(__file__).resolve().parents[2]


class NativeSearchError(RuntimeError):
    """An explicitly configured or discovered native engine failed closed."""


def native_search_executable() -> Path | None:
    override = os.getenv("MORPHEUS_NATIVE_SEARCH_EXECUTABLE")
    suffix = ".exe" if os.name == "nt" else ""
    candidates = (
        [Path(override)] if override else [
            _ROOT / "bin" / ("morpheus_native_search" + suffix),
            _ROOT / "build" / "core" / ("morpheus_native_search" + suffix),
            _ROOT / "build" / "core" / "Release" / ("morpheus_native_search" + suffix),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    if not override:
        executable = shutil.which("morpheus_native_search")
        if executable:
            return Path(executable)
    return None


def select_native_combinations(
    spec: WorkloadSpec,
    options: list[list[str]],
    *,
    strategy: SearchStrategy,
    max_candidates: int,
    beam_width: int,
) -> tuple[SearchStrategy, list[tuple[str, ...]]] | None:
    """Select configurations using C++ if installed; otherwise return None.

    MORPHEUS_SEARCH_BACKEND=native requires native code and never falls back.
    MORPHEUS_SEARCH_BACKEND=python explicitly uses the old research path.
    MORPHEUS_SEARCH_BACKEND=auto (default) prefers compiled C++ where present.
    """
    mode = os.getenv("MORPHEUS_SEARCH_BACKEND", "auto").strip().lower()
    if mode not in {"auto", "native", "python"}:
        raise NativeSearchError("MORPHEUS_SEARCH_BACKEND must be auto, native or python")
    if mode == "python":
        return None
    executable = native_search_executable()
    if executable is None:
        if mode == "native":
            raise NativeSearchError(
                "Native C++20 search is required but morpheus_native_search is not built; "
                "build with cmake -S core -B build/core && cmake --build build/core"
            )
        return None

    if any(not items for items in options):
        raise NativeSearchError("native search received an unsupported query")
    profile = CALIBRATIONS.active()
    memory_limit = spec.constraints.memory_mb
    lines = [
        "MORPHEUS_NATIVE_SEARCH_V1",
        f"{strategy.value} {max_candidates} {beam_width} {len(options)} "
        f"{format(memory_limit, '.17g') if memory_limit is not None else '-1'}",
    ]
    for query, names in zip(spec.queries, options, strict=True):
        lines.append(f"{format(query.weight, '.17g')} {len(names)}")
        for name in names:
            estimate = estimate_query_latency_us(spec, query, name, profile=profile)
            physical_memory_mb = (
                0.0 if query.kind in _MUTATIONS else
                predicted_index_bytes(spec, name, query.field) / (1024 * 1024)
            )
            lines.append(
                f"{name} {format(estimate.value, '.17g')} "
                f"{format(physical_memory_mb, '.17g')}"
            )

    try:
        completed = subprocess.run(
            [str(executable)],
            input="\n".join(lines) + "\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeSearchError(f"native optimizer could not execute: {exc}") from exc
    if completed.returncode != 0:
        raise NativeSearchError(
            f"native optimizer refused the workload: {completed.stderr.strip()[:500]}"
        )
    output = completed.stdout.splitlines()
    if not output:
        raise NativeSearchError("native optimizer returned an empty response")
    header = output[0].split()
    if len(header) != 3 or header[0] != "OK":
        raise NativeSearchError("native optimizer output has an invalid header")
    try:
        selected = SearchStrategy(header[1])
        total = int(header[2])
    except (ValueError, TypeError) as exc:
        raise NativeSearchError("native optimizer returned invalid strategy/count") from exc
    if selected == SearchStrategy.AUTO or not 1 <= total <= max_candidates:
        raise NativeSearchError("native optimizer returned an invalid candidate budget")
    if len(output) != total + 1:
        raise NativeSearchError("native optimizer returned a truncated candidate set")

    configurations: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for line in output[1:]:
        tokens = line.split()
        if len(tokens) != len(options) + 1 or tokens[0] != "C":
            raise NativeSearchError("native optimizer returned an invalid configuration")
        try:
            indices = [int(value) for value in tokens[1:]]
            if any(index < 0 or index >= len(options[q])
                   for q, index in enumerate(indices)):
                raise ValueError("option index out of range")
            combination = tuple(options[q][index] for q, index in enumerate(indices))
        except ValueError as exc:
            raise NativeSearchError("native optimizer returned invalid option indexes") from exc
        if combination in seen:
            raise NativeSearchError("native optimizer returned duplicate configurations")
        configurations.append(combination)
        seen.add(combination)
    return selected, configurations
