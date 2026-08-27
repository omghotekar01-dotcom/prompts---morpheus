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


def _positive_ints(raw: str) -> list[int]:
    values: list[int] = []
    for token in raw.split(","):
        try:
            value = int(token.strip())
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid integer: {token!r}") from exc
        if value <= 0:
            raise argparse.ArgumentTypeError("matrix values must be positive")
        values.append(value)
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def _run_once(
    executable: Path,
    *,
    n: int,
    operations: int,
    seed: int,
    repetitions: int,
    warmup: int,
    timeout_seconds: int,
) -> tuple[dict[str, Any], list[str]]:
    command = [
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
            f"calibration command failed with exit {process.returncode}: {process.stderr[-4000:]}"
        )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("calibration executable did not emit valid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("measurements"), list):
        raise RuntimeError("calibration JSON is missing the measurements array")
    return payload, command


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a reproducible MORPHEUS primitive-calibration matrix and preserve raw evidence."
    )
    parser.add_argument("executable", type=Path, help="Path to morpheus_calibrate executable")
    parser.add_argument("--sizes", type=_positive_ints, default=[1000, 10000, 100000])
    parser.add_argument("--seeds", type=_positive_ints, default=[1337, 7331, 2026])
    parser.add_argument("--ops", type=int, default=50000)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark-results/calibration"))
    args = parser.parse_args()

    executable = args.executable.resolve()
    if not executable.is_file():
        raise SystemExit(f"calibration executable not found: {executable}")
    if args.ops <= 0 or args.repetitions <= 0 or args.warmup < 0 or args.timeout <= 0:
        raise SystemExit("ops/repetitions/timeout must be positive and warmup must be non-negative")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    machine_profile = capture()
    machine_path = output_dir / "machine-profile.json"
    machine_path.write_text(json.dumps(machine_profile, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    source_commit = _git_commit()
    entries: list[dict[str, Any]] = []
    for n in args.sizes:
        for seed in args.seeds:
            payload, command = _run_once(
                executable,
                n=n,
                operations=args.ops,
                seed=seed,
                repetitions=args.repetitions,
                warmup=args.warmup,
                timeout_seconds=args.timeout,
            )
            file_name = f"calibration-n{n}-seed{seed}.json"
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
                    "command": command,
                    "evidence_state": payload.get("evidence_state"),
                    "protocol": payload.get("protocol"),
                }
            )

    manifest = {
        "schema_version": 1,
        "protocol": "morpheus-calibration-matrix-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_commit": source_commit,
        "executable": str(executable),
        "executable_sha256": _sha256(executable),
        "machine_profile_file": machine_path.name,
        "machine_profile_sha256": _sha256(machine_path),
        "runs": entries,
        "truth_note": (
            "This manifest preserves repeated local-process primitive measurements and provenance. "
            "It is not automatically publication-grade or end-to-end generated-artifact evidence."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
