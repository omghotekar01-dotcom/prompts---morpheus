from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.reproducibility import EvidenceFile, build_reproducibility_manifest  # noqa: E402


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


def _parse_input(raw: str) -> EvidenceFile:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("evidence input must use ROLE=PATH")
    role, path = raw.split("=", 1)
    role = role.strip()
    path = path.strip()
    if not role or not path:
        raise argparse.ArgumentTypeError("evidence input must use non-empty ROLE=PATH")
    return EvidenceFile(role, Path(path))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a content-hash manifest linking MORPHEUS experiment evidence files."
    )
    parser.add_argument(
        "evidence",
        nargs="+",
        type=_parse_input,
        metavar="ROLE=PATH",
        help="Evidence input, e.g. workload=examples/users-demo.yaml",
    )
    parser.add_argument("--output", type=Path, default=Path("morpheus-repro-manifest.json"))
    args = parser.parse_args()

    manifest = build_reproducibility_manifest(args.evidence, source_commit=_git_commit())
    manifest["created_at"] = datetime.now(UTC).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
