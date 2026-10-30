from __future__ import annotations

"""Versioned Java 17+ physical-plan scoring adapter.

The imported C++ search produces candidates. The cost-estimation compatibility
layer still computes predicted metrics, but Java owns objective scoring and
hard feasibility decisions when MORPHEUS_PLAN_SCORER=java (or auto with a
compiled Java class available). No shell, generated source execution or
fabricated measurement is involved.
"""

import math
import os
import shutil
import subprocess
from pathlib import Path

from .models import CandidateResult, WorkloadSpec

_ROOT = Path(__file__).resolve().parents[2]
_MAIN_CLASS = "com.morpheus.dsa.PlanScorer"
_PROTOCOL = "MORPHEUS_JAVA_SCORE_V1"


class JavaPlanScorerError(RuntimeError):
    """Java scorer was explicitly required or refused a protocol request."""


def java_plan_scorer_command() -> list[str] | None:
    java = shutil.which("java")
    classes = Path(os.environ.get("MORPHEUS_JAVA_CLASSES", str(_ROOT / "build" / "java")))
    if java is None or not (classes / "com" / "morpheus" / "dsa" / "PlanScorer.class").is_file():
        return None
    return [java, "-cp", str(classes), _MAIN_CLASS]


def apply_java_plan_scores(
    spec: WorkloadSpec, candidates: list[CandidateResult],
) -> list[CandidateResult] | None:
    """Score complete candidate metrics using the deterministic Java runtime.

    Returns None only when Python fallback is explicitly selected or auto mode
    has no compiled Java class. A present but faulty Java engine is fail-closed.
    Metric provenance remains MODEL_PREDICTION, never actual dataset speed.
    """
    mode = os.environ.get("MORPHEUS_PLAN_SCORER", "auto").strip().lower()
    if mode not in {"auto", "python", "java"}:
        raise JavaPlanScorerError("MORPHEUS_PLAN_SCORER must be auto, java or python")
    if mode == "python" or not candidates:
        return None
    command = java_plan_scorer_command()
    if command is None:
        if mode == "java":
            raise JavaPlanScorerError(
                "Java physical-plan scoring required; install Java 17+, compile "
                "java/src/com/morpheus/dsa/PlanScorer.java to build/java or set "
                "MORPHEUS_JAVA_CLASSES to the compiled classes directory"
            )
        return None

    constraints = spec.constraints
    objective = spec.objective
    sentinel = lambda limit: "-1" if limit is None else format(limit, ".17g")
    lines = [
        _PROTOCOL,
        str(len(candidates)),
        " ".join((
            sentinel(constraints.memory_mb), sentinel(constraints.p99_latency_us),
            sentinel(constraints.build_time_ms), format(constraints.update_rate, ".17g"),
        )),
        " ".join(format(value, ".17g") for value in (
            objective.latency, objective.memory, objective.update, objective.build,
        )),
    ]
    for item in candidates:
        lines.append(" ".join(format(value, ".17g") for value in (
            item.predicted_latency_us, item.predicted_memory_mb,
            item.predicted_build_ms, item.predicted_update_us,
        )))
    try:
        result = subprocess.run(
            command, input="\n".join(lines) + "\n", text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise JavaPlanScorerError(f"Java scorer process unavailable: {error}") from error
    if result.returncode != 0:
        raise JavaPlanScorerError(
            f"Java physical-plan scoring failed: {result.stderr.strip()[:350]}"
        )
    output = result.stdout.splitlines()
    if len(output) != len(candidates) + 1 or output[0] != f"OK {len(candidates)}":
        raise JavaPlanScorerError("Java scorer returned an invalid or truncated response")

    updated = []
    for position, (item, line) in enumerate(zip(candidates, output[1:], strict=True)):
        parts = line.split()
        if len(parts) != 3 or parts[0] != "R":
            raise JavaPlanScorerError(f"malformed Java candidate response at {position}")
        try:
            score = float(parts[1])
            flags = int(parts[2])
        except ValueError as error:
            raise JavaPlanScorerError(f"invalid Java score or flags at {position}") from error
        if not math.isfinite(score) or score < 0 or flags < 0 or flags > 7:
            raise JavaPlanScorerError(f"out-of-range Java score or flags at {position}")

        reasons = []
        if flags & 1:
            reasons.append(
                f"predicted index memory {item.predicted_memory_mb:.2f} MB "
                f"exceeds hard limit {constraints.memory_mb:.2f} MB"
            )
        if flags & 2:
            reasons.append(
                f"predicted aggregate latency {item.predicted_latency_us:.3f} us "
                f"exceeds hard p99 proxy {constraints.p99_latency_us:.3f} us"
            )
        if flags & 4:
            reasons.append(
                f"predicted build {item.predicted_build_ms:.2f} ms "
                f"exceeds hard limit {constraints.build_time_ms:.2f} ms"
            )
        updated.append(item.model_copy(update={
            "score": round(score, 9),
            "feasible": flags == 0,
            "rejection_reasons": reasons,
        }))
    return updated
