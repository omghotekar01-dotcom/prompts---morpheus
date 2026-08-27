#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .build_release_manifest import build_manifest

MAX_PACKAGE_FILE_BYTES = 64 * 1024 * 1024
FIXED_ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(role: str, source: Path, index: int) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in role.strip())
    cleaned = cleaned.strip("._") or f"artifact-{index}"
    suffix = source.suffix if len(source.suffix) <= 16 else ""
    return f"{index:03d}-{cleaned}{suffix}"


def _validate_local_file(path: Path) -> bytes:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"evidence file does not exist: {path}")
    size = resolved.stat().st_size
    if size > MAX_PACKAGE_FILE_BYTES:
        raise ValueError(f"evidence file exceeds {MAX_PACKAGE_FILE_BYTES} byte package limit: {path}")
    return resolved.read_bytes()


def build_evidence_package(descriptor: dict[str, Any], output_dir: Path, *, zip_output: Path | None = None) -> dict[str, Any]:
    """Build a deterministic release evidence directory and optional ZIP.

    The descriptor extends the normal release-manifest input by allowing each
    artifact entry to include a local ``path``. The file bytes must hash to the
    declared SHA-256 before packaging. Claim gates are evaluated by the same
    release-manifest implementation, so the package fails closed when evidence
    roles are incomplete. Packaging proves byte linkage, not scientific truth.
    """

    artifacts = descriptor.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("artifacts must be an array")

    packaged: list[dict[str, Any]] = []
    package_files: list[tuple[str, bytes]] = []
    manifest_artifacts: list[dict[str, str]] = []
    for index, item in enumerate(artifacts, start=1):
        if not isinstance(item, dict):
            raise ValueError("artifact entries must be objects")
        role = str(item.get("role", "")).strip()
        expected = str(item.get("sha256", "")).strip().lower()
        raw_path = item.get("path")
        if not role or not expected or raw_path is None:
            raise ValueError("each package artifact requires role, sha256 and path")
        source = Path(str(raw_path))
        data = _validate_local_file(source)
        actual = _sha256_bytes(data)
        if actual != expected:
            raise ValueError(f"artifact hash mismatch for role {role!r}: expected {expected}, got {actual}")
        package_name = _safe_name(role, source, index)
        package_files.append((f"evidence/{package_name}", data))
        packaged.append(
            {
                "role": role,
                "source_name": source.name,
                "package_path": f"evidence/{package_name}",
                "sha256": actual,
                "size_bytes": len(data),
            }
        )
        manifest_artifacts.append({"role": role, "sha256": actual})

    manifest_input = {
        "version": descriptor.get("version"),
        "commit": descriptor.get("commit"),
        "artifacts": manifest_artifacts,
        "claims": descriptor.get("claims", []),
    }
    manifest = build_manifest(manifest_input)
    index_core = {
        "schema": "morpheus-evidence-package-v1",
        "release_manifest_sha256": manifest["manifest_sha256"],
        "release_state": manifest["release_state"],
        "files": sorted(packaged, key=lambda item: (item["role"], item["package_path"])),
        "truth_boundaries": [
            "The package verifies byte identity and evidence-role linkage only.",
            "A satisfied claim role gate does not replace benchmark-methodology, security, legal, patentability, or peer review.",
        ],
    }
    index_core["package_index_sha256"] = hashlib.sha256(
        json.dumps(index_core, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    output_dir = output_dir.resolve()
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError(f"output path exists and is not a directory: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "evidence").mkdir()

    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
    index_bytes = (json.dumps(index_core, sort_keys=True, indent=2) + "\n").encode("utf-8")
    (output_dir / "release-manifest.json").write_bytes(manifest_bytes)
    (output_dir / "evidence-index.json").write_bytes(index_bytes)
    for relative, data in package_files:
        destination = output_dir / PurePosixPath(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)

    if zip_output is not None:
        zip_output = zip_output.resolve()
        zip_output.parent.mkdir(parents=True, exist_ok=True)
        members = [
            ("release-manifest.json", manifest_bytes),
            ("evidence-index.json", index_bytes),
            *sorted(package_files, key=lambda item: item[0]),
        ]
        with zipfile.ZipFile(zip_output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in members:
                info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, data)
        index_core["zip"] = {
            "path": str(zip_output),
            "sha256": _sha256_bytes(zip_output.read_bytes()),
            "size_bytes": zip_output.stat().st_size,
            "deterministic_timestamp": list(FIXED_ZIP_TIMESTAMP),
        }

    return {"manifest": manifest, "package_index": index_core}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic, claim-gated MORPHEUS evidence package.")
    parser.add_argument("descriptor", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--zip", dest="zip_output", type=Path)
    args = parser.parse_args()
    try:
        descriptor = json.loads(args.descriptor.read_text(encoding="utf-8"))
        if not isinstance(descriptor, dict):
            raise ValueError("descriptor must be a JSON object")
        result = build_evidence_package(descriptor, args.output_dir, zip_output=args.zip_output)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"morpheus evidence package: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result["package_index"], sort_keys=True))
    return 0 if result["manifest"]["release_state"] == "CLAIMS_EVIDENCE_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
