#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.research_suite import PairedObservation, analyze_paired_measurements, freeze_experiment_matrix
from capture_machine_profile import capture as capture_machine_profile


PAIRINGS: tuple[tuple[str, str, str], ...] = (
    ("hash_build", "morpheus_robin_hood_hash", "std_unordered_map"),
    ("hash_point_lookup", "morpheus_robin_hood_hash", "std_unordered_map"),
    ("tree_build", "morpheus_bplus_tree", "std_map"),
    ("tree_point_lookup", "morpheus_bplus_tree", "std_map"),
    ("tree_range_scan", "morpheus_bplus_tree", "std_map"),
)
PAIR_OPERATION = {
    "hash_build": "build",
    "hash_point_lookup": "point_lookup",
    "tree_build": "build",
    "tree_point_lookup": "point_lookup",
    "tree_range_scan": "range_scan",
}


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_once(
    executable: Path,
    *,
    n: int,
    operations: int,
    seed: int,
    repetitions: int,
    warmup: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    process = subprocess.run(
        [
            str(executable),
            "--n",
            str(n),
            "--ops",
            str(operations),
            "--seed",
            str(seed),
            "--repetitions",
            str(repetitions),
            "--warmup",
            str(warmup),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"baseline executable failed for n={n}, seed={seed}, rc={process.returncode}: {process.stderr.strip()}"
        )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"baseline executable returned invalid JSON for n={n}, seed={seed}") from exc
    if payload.get("protocol") != "morpheus-baseline-bench-v1":
        raise RuntimeError("unexpected baseline benchmark protocol")
    return payload


def _measurement_map(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for item in payload.get("measurements", []):
        if not isinstance(item, dict):
            continue
        key = (str(item.get("system", "")), str(item.get("operation", "")))
        if not all(key):
            continue
        if key in result:
            raise RuntimeError(f"duplicate measurement in baseline payload: {key}")
        result[key] = item
    return result


def run_matrix(
    executable: Path,
    *,
    sizes: list[int],
    seeds: list[int],
    operations: int,
    repetitions: int,
    warmup: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    if not executable.is_file():
        raise ValueError(f"baseline executable does not exist: {executable}")
    if not sizes or any(value <= 0 for value in sizes):
        raise ValueError("sizes must contain positive integers")
    if not seeds:
        raise ValueError("at least one seed is required")
    if operations <= 0 or repetitions <= 0 or warmup < 0:
        raise ValueError("operations/repetitions must be positive and warmup non-negative")

    frozen = freeze_experiment_matrix(
        study_id="rq-baseline-standard-library-v1",
        hypothesis=(
            "MORPHEUS primitives have workload-dependent performance trade-offs relative to matched C++ standard-library baselines"
        ),
        metric="ns_per_operation",
        lower_is_better=True,
        repetitions=repetitions,
        seeds=seeds,
        axes={"record_count": sizes},
    )

    runs: list[dict[str, Any]] = []
    observations: dict[str, list[PairedObservation]] = {name: [] for name, _, _ in PAIRINGS}
    for n in sizes:
        for seed in seeds:
            payload = _run_once(
                executable,
                n=n,
                operations=operations,
                seed=seed,
                repetitions=repetitions,
                warmup=warmup,
                timeout_seconds=timeout_seconds,
            )
            measurements = _measurement_map(payload)
            run_label = f"n={n};seed={seed}"
            for pair_name, treatment_system, baseline_system in PAIRINGS:
                operation = PAIR_OPERATION[pair_name]
                treatment = measurements.get((treatment_system, operation))
                baseline = measurements.get((baseline_system, operation))
                if treatment is None or baseline is None:
                    raise RuntimeError(
                        f"missing paired measurement for {pair_name}: treatment={treatment_system}, baseline={baseline_system}, operation={operation}"
                    )
                observations[pair_name].append(
                    PairedObservation(
                        label=run_label,
                        baseline=float(baseline["median_ns"]),
                        treatment=float(treatment["median_ns"]),
                    )
                )
            runs.append({"n": n, "seed": seed, "payload": payload, "payload_sha256": _sha256_json(payload)})

    analyses: dict[str, Any] = {}
    for pair_name, treatment_system, baseline_system in PAIRINGS:
        analyses[pair_name] = {
            "treatment": treatment_system,
            "baseline": baseline_system,
            "operation": PAIR_OPERATION[pair_name],
            "analysis": analyze_paired_measurements(
                metric="median_ns_per_operation",
                observations=observations[pair_name],
                lower_is_better=True,
                bootstrap_rounds=max(500, min(10_000, 1000 * len(observations[pair_name]))),
                bootstrap_seed=1337,
            ).as_dict(),
        }

    machine = capture_machine_profile()
    raw_core = {
        "protocol": "morpheus-standard-baseline-matrix-v1",
        "experiment_manifest": frozen.as_dict(),
        "sizes": sizes,
        "seeds": seeds,
        "operations": operations,
        "repetitions": repetitions,
        "warmup": warmup,
        "runs": runs,
    }
    raw_sha = _sha256_json(raw_core)
    baseline_manifest = {
        "schema": "morpheus-baseline-manifest-v1",
        "baseline_class": "CXX_STANDARD_LIBRARY",
        "systems": {
            "std_unordered_map": "C++ standard-library unordered associative container",
            "std_map": "C++ standard-library ordered associative container",
        },
        "treatments": {
            "morpheus_robin_hood_hash": "MORPHEUS Robin Hood hash implementation",
            "morpheus_bplus_tree": "MORPHEUS B+ tree implementation",
        },
        "scope": "Paired local process baseline only; specialist databases/index libraries are a separate external-baseline tier.",
    }
    statistical_summary = {
        "schema": "morpheus-standard-baseline-statistics-v1",
        "source_raw_measurements_sha256": raw_sha,
        "comparisons": analyses,
        "evidence_state": "ANALYZED_PAIRED_LOCAL_STANDARD_LIBRARY_MEASUREMENTS",
        "truth_note": (
            "These summaries characterize only the declared machine, executable, seeds and matrix. They do not establish universal or state-of-the-art superiority."
        ),
    }
    return {
        "experiment_manifest": frozen.as_dict(),
        "machine_profile": machine,
        "baseline_manifest": baseline_manifest,
        "raw_measurements": raw_core,
        "raw_measurements_sha256": raw_sha,
        "statistical_summary": statistical_summary,
        "evidence_state": "MEASURED_LOCAL_PAIRED_BASELINE_MATRIX",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic paired MORPHEUS-vs-standard-library baseline matrix.")
    parser.add_argument("executable", type=Path)
    parser.add_argument("--sizes", nargs="+", type=int, default=[1_000, 10_000, 100_000])
    parser.add_argument("--seeds", nargs="+", type=int, default=[1337, 2027, 4242])
    parser.add_argument("--ops", type=int, default=20_000)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = run_matrix(
            args.executable.resolve(),
            sizes=args.sizes,
            seeds=args.seeds,
            operations=args.ops,
            repetitions=args.repetitions,
            warmup=args.warmup,
            timeout_seconds=args.timeout,
        )
    except (OSError, subprocess.SubprocessError, TypeError, ValueError, RuntimeError) as exc:
        print(f"morpheus baseline matrix: {exc}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "experiment_manifest.json": result["experiment_manifest"],
        "machine_profile.json": result["machine_profile"],
        "baseline_manifest.json": result["baseline_manifest"],
        "raw_measurements.json": result["raw_measurements"],
        "statistical_summary.json": result["statistical_summary"],
    }
    artifact_index: list[dict[str, Any]] = []
    for name, payload in files.items():
        text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
        path = args.output_dir / name
        path.write_text(text, encoding="utf-8")
        artifact_index.append(
            {
                "name": name,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "size_bytes": len(text.encode("utf-8")),
            }
        )
    index = {
        "schema": "morpheus-baseline-evidence-index-v1",
        "artifacts": sorted(artifact_index, key=lambda item: item["name"]),
        "evidence_state": result["evidence_state"],
    }
    (args.output_dir / "evidence_index.json").write_text(json.dumps(index, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(index, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
