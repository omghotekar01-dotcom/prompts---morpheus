from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = Path(__file__).resolve().parent
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))

from capture_machine_profile import capture  # noqa: E402


EXPECTED_IMPLEMENTATION_IDS: dict[str, str] = {
    "robin_hood_hash": "morpheus.RobinHoodHashIndex.v1",
    "sorted_array": "morpheus.MutableSortedArrayIndex.v1",
    "ordered_tree": "morpheus.BPlusTreeIndex.rebalanced.v1",
    "radix_trie": "morpheus.MutableMultiPrefixTrie.v1",
    "bitmap": "morpheus.CompressedBitmapFilterIndex.adaptive32.v1",
}
EXPECTED_DISTRIBUTIONS = {"uniform", "sequential", "hotspot", "zipf"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _validate_payload(payload: dict[str, Any], requested_distributions: set[str]) -> dict[str, Any]:
    if payload.get("protocol") != "morpheus-distribution-calibration-v1":
        raise RuntimeError(f"unexpected distribution calibration protocol: {payload.get('protocol')!r}")
    if payload.get("schema_version") != 4:
        raise RuntimeError("distribution calibration schema_version must be 4")
    if payload.get("distribution_protocol") != "morpheus-access-distribution-v1":
        raise RuntimeError("distribution calibration omitted canonical distribution protocol")

    measurements = payload.get("measurements")
    if not isinstance(measurements, list) or not measurements:
        raise RuntimeError("distribution calibration measurements must be non-empty")

    seen: set[tuple[str, str, str, str]] = set()
    observed_distributions: set[str] = set()
    implementation_ids: set[str] = set()
    for index, measurement in enumerate(measurements):
        if not isinstance(measurement, dict):
            raise RuntimeError(f"measurement[{index}] must be an object")
        primitive = str(measurement.get("primitive", ""))
        implementation_id = str(measurement.get("implementation_id", ""))
        operation = str(measurement.get("operation", ""))
        distribution = measurement.get("access_distribution")
        if not isinstance(distribution, dict):
            raise RuntimeError(f"measurement[{index}] is not distribution-bound")
        kind = str(distribution.get("kind", ""))
        if kind not in EXPECTED_DISTRIBUTIONS:
            raise RuntimeError(f"measurement[{index}] has unsupported distribution {kind!r}")
        expected_implementation = EXPECTED_IMPLEMENTATION_IDS.get(primitive)
        if expected_implementation is None:
            raise RuntimeError(f"measurement[{index}] emitted unexpected primitive {primitive!r}")
        if implementation_id != expected_implementation:
            raise RuntimeError(
                f"implementation mismatch for {primitive}: expected {expected_implementation!r}, got {implementation_id!r}"
            )
        canonical_distribution = json.dumps(distribution, sort_keys=True, separators=(",", ":"))
        key = (primitive, operation, kind, canonical_distribution)
        if key in seen:
            raise RuntimeError(f"duplicate distribution-bound calibration cell: {key}")
        seen.add(key)
        observed_distributions.add(kind)
        implementation_ids.add(implementation_id)

        if kind == "zipf" and "zipf_theta" not in distribution:
            raise RuntimeError("zipf measurement omitted zipf_theta")
        if kind == "hotspot" and not {"hotspot_fraction", "hotspot_probability"} <= set(distribution):
            raise RuntimeError("hotspot measurement omitted hotspot parameters")

    if observed_distributions != requested_distributions:
        raise RuntimeError(
            f"distribution coverage mismatch: expected {sorted(requested_distributions)}, got {sorted(observed_distributions)}"
        )
    return {
        "measurement_count": len(measurements),
        "implementation_ids": sorted(implementation_ids),
        "distributions": sorted(observed_distributions),
    }


def _run_once(
    executable: Path,
    *,
    n: int,
    operations: int,
    seed: int,
    repetitions: int,
    warmup: int,
    distributions: list[str],
    zipf_theta: float,
    hotspot_fraction: float,
    hotspot_probability: float,
    timeout_seconds: int,
) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    command = [
        str(executable),
        "--n", str(n),
        "--ops", str(operations),
        "--seed", str(seed),
        "--repetitions", str(repetitions),
        "--warmup", str(warmup),
        "--distributions", ",".join(distributions),
        "--zipf-theta", str(zipf_theta),
        "--hotspot-fraction", str(hotspot_fraction),
        "--hotspot-probability", str(hotspot_probability),
    ]
    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        cwd=executable.parent,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"distribution calibration failed with exit {process.returncode}: {process.stderr[-4000:]}"
        )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("distribution calibration executable did not emit valid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("distribution calibration payload must be an object")
    validation = _validate_payload(payload, set(distributions))
    return payload, command, validation


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run implementation- and access-distribution-bound MORPHEUS primitive calibration."
    )
    parser.add_argument("executable", type=Path)
    parser.add_argument("--sizes", nargs="+", type=int, default=[1000, 10000])
    parser.add_argument("--seeds", nargs="+", type=int, default=[1337, 2027, 9001])
    parser.add_argument(
        "--distributions",
        nargs="+",
        choices=sorted(EXPECTED_DISTRIBUTIONS),
        default=["uniform", "sequential", "hotspot", "zipf"],
    )
    parser.add_argument("--ops", type=int, default=10000)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--zipf-theta", type=float, default=0.99)
    parser.add_argument("--hotspot-fraction", type=float, default=0.10)
    parser.add_argument("--hotspot-probability", type=float, default=0.80)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    executable = args.executable.resolve()
    if not executable.is_file():
        raise SystemExit(f"distribution calibration executable not found: {executable}")
    if any(value <= 1 for value in args.sizes):
        raise SystemExit("all sizes must be >= 2")
    if not args.seeds or any(seed < 0 for seed in args.seeds):
        raise SystemExit("at least one non-negative seed is required")
    if args.ops <= 0 or args.repetitions <= 0 or args.warmup < 0 or args.timeout <= 0:
        raise SystemExit("ops/repetitions/timeout must be positive and warmup non-negative")

    distributions = sorted(set(args.distributions))
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    machine = capture()
    machine_path = output_dir / "machine-profile.json"
    machine_path.write_text(json.dumps(machine, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    entries: list[dict[str, Any]] = []
    implementation_ids: set[str] = set()
    for n in args.sizes:
        for seed in args.seeds:
            payload, command, validation = _run_once(
                executable,
                n=n,
                operations=args.ops,
                seed=seed,
                repetitions=args.repetitions,
                warmup=args.warmup,
                distributions=distributions,
                zipf_theta=args.zipf_theta,
                hotspot_fraction=args.hotspot_fraction,
                hotspot_probability=args.hotspot_probability,
                timeout_seconds=args.timeout,
            )
            implementation_ids.update(validation["implementation_ids"])
            file_name = f"distribution-calibration-n{n}-seed{seed}.json"
            path = output_dir / file_name
            path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            entries.append(
                {
                    "file": file_name,
                    "sha256": _sha256(path),
                    "record_count": n,
                    "seed": seed,
                    "operations": args.ops,
                    "repetitions": args.repetitions,
                    "warmup": args.warmup,
                    "distributions": validation["distributions"],
                    "measurement_count": validation["measurement_count"],
                    "implementation_ids": validation["implementation_ids"],
                    "command": command,
                    "evidence_state": payload.get("evidence_state"),
                }
            )

    manifest = {
        "schema_version": 1,
        "protocol": "morpheus-distribution-calibration-matrix-v1",
        "distribution_protocol": "morpheus-access-distribution-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_commit": _git_commit(),
        "executable": str(executable),
        "executable_sha256": _sha256(executable),
        "machine_profile_file": machine_path.name,
        "machine_profile_sha256": _sha256(machine_path),
        "machine_fingerprint_sha256": machine.get("machine_fingerprint_sha256"),
        "distributions": distributions,
        "zipf_theta": args.zipf_theta,
        "hotspot_fraction": args.hotspot_fraction,
        "hotspot_probability": args.hotspot_probability,
        "implementation_ids": sorted(implementation_ids),
        "runs": entries,
        "evidence_state": "CONTENT_HASHED_DISTRIBUTION_BOUND_PRIMITIVE_CALIBRATION_MATRIX",
        "truth_note": (
            "Each query/update measurement is bound to exact physical implementation, record count and access-distribution parameters. "
            "This remains primitive-level machine-local evidence and does not establish end-to-end generated-candidate performance."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
