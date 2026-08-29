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

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (REPO_ROOT, BACKEND_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.evidence_validation import validate_cross_artifact_links
from app.generated_migration_release_evidence import validate_generated_migration_cross_links
from app.generated_migration_transition_package import validate_generated_migration_transition_package_links
from app.release_evidence_validation import validate_release_evidence_bytes
from app.rq7_confirmatory_links import validate_rq7_confirmatory_cross_links
from release.build_release_manifest import build_manifest

MAX_PACKAGE_FILE_BYTES = 64 * 1024 * 1024
FIXED_ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def _try_json(data: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def build_evidence_package(descriptor: dict[str, Any], output_dir: Path, *, zip_output: Path | None = None) -> dict[str, Any]:
    """Build a deterministic release evidence directory and optional ZIP.

    Each descriptor artifact must provide ``role``, ``path`` and its declared
    SHA-256. Before packaging, MORPHEUS verifies the bytes, applies a structural
    validator for the evidence role, and checks cross-artifact hash links that
    are locally decidable. Artifact roles are unique so cross-link validation
    cannot inspect one instance while a second conflicting instance is packaged.
    The release claim gate then operates on artifact roles actually present.
    """

    artifacts = descriptor.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("artifacts must be an array")

    packaged: list[dict[str, Any]] = []
    package_files: list[tuple[str, bytes]] = []
    manifest_artifacts: list[dict[str, str]] = []
    validation_context: dict[str, dict[str, Any]] = {}
    seen_roles: set[str] = set()
    for index, item in enumerate(artifacts, start=1):
        if not isinstance(item, dict):
            raise ValueError("artifact entries must be objects")
        role = str(item.get("role", "")).strip()
        expected = str(item.get("sha256", "")).strip().lower()
        raw_path = item.get("path")
        if not role or not expected or raw_path is None:
            raise ValueError("each package artifact requires role, sha256 and path")
        if role in seen_roles:
            raise ValueError(f"duplicate evidence artifact role: {role}")
        seen_roles.add(role)
        source = Path(str(raw_path))
        data = _validate_local_file(source)
        actual = _sha256_bytes(data)
        if actual != expected:
            raise ValueError(f"artifact hash mismatch for role {role!r}: expected {expected}, got {actual}")

        structural = validate_release_evidence_bytes(role, data)
        if not structural.valid:
            raise ValueError(f"artifact structural validation failed for role {role!r}: {'; '.join(structural.details)}")

        package_name = _safe_name(role, source, index)
        package_files.append((f"evidence/{package_name}", data))
        json_payload = _try_json(data)
        canonical_json_sha = _canonical_json_sha256(json_payload) if json_payload is not None else None
        packaged.append(
            {
                "role": role,
                "source_name": source.name,
                "package_path": f"evidence/{package_name}",
                "sha256": actual,
                "canonical_json_sha256": canonical_json_sha,
                "size_bytes": len(data),
                "structural_validation": structural.as_dict(),
            }
        )
        manifest_artifacts.append({"role": role, "sha256": actual})
        validation_context[role] = {
            "sha256": actual,
            "canonical_json_sha256": canonical_json_sha,
            "json": json_payload,
        }

    link_errors = [
        *validate_cross_artifact_links(validation_context),
        *validate_generated_migration_cross_links(validation_context),
        *validate_generated_migration_transition_package_links(validation_context),
        *validate_rq7_confirmatory_cross_links(validation_context),
    ]
    if link_errors:
        raise ValueError("cross-artifact validation failed: " + "; ".join(link_errors))

    manifest_input = {
        "version": descriptor.get("version"),
        "commit": descriptor.get("commit"),
        "artifacts": manifest_artifacts,
        "claims": descriptor.get("claims", []),
    }
    manifest = build_manifest(manifest_input)
    index_core = {
        "schema": "morpheus-evidence-package-v2",
        "release_manifest_sha256": manifest["manifest_sha256"],
        "release_state": manifest["release_state"],
        "files": sorted(packaged, key=lambda item: (item["role"], item["package_path"])),
        "cross_artifact_validation": "PASSED",
        "truth_boundaries": [
            "The package verifies byte identity, structural contracts and locally decidable hash links.",
            "RQ7 packages bind experiment, campaign, summary, transition attestation, H7 analysis, measurement-environment and machine/toolchain identities when those roles are present.",
            "Structural validity does not independently establish measurement methodology, external reproducibility, novelty, patentability or scientific superiority.",
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
