from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


MAX_MANIFEST_INPUT_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class EvidenceFile:
    role: str
    path: Path


@dataclass(frozen=True)
class EvidenceFileDigest:
    role: str
    name: str
    sha256: str
    size_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "name": self.name,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def _valid_hex(value: str | None, length: int) -> bool:
    if value is None or len(value) != length:
        return False
    return all(ch in "0123456789abcdef" for ch in value.lower())


def hash_evidence_files(files: Iterable[EvidenceFile]) -> list[EvidenceFileDigest]:
    """Hash external experiment evidence without upgrading its truth state.

    A content digest proves byte identity only. It does not prove that a file's
    measurements were collected correctly, that the experiment was unbiased, or
    that the artifact was independently attested.
    """

    results: list[EvidenceFileDigest] = []
    seen_roles: set[str] = set()
    for item in files:
        role = item.role.strip()
        if not role:
            raise ValueError("evidence file role cannot be empty")
        if role in seen_roles:
            raise ValueError(f"duplicate evidence role: {role}")
        seen_roles.add(role)

        path = item.path.resolve()
        if not path.is_file():
            raise ValueError(f"evidence file does not exist: {item.path}")
        size = path.stat().st_size
        if size > MAX_MANIFEST_INPUT_BYTES:
            raise ValueError(
                f"evidence file exceeds {MAX_MANIFEST_INPUT_BYTES} byte manifest hashing limit: {item.path}"
            )

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        results.append(
            EvidenceFileDigest(
                role=role,
                name=path.name,
                sha256=digest.hexdigest(),
                size_bytes=size,
            )
        )

    results.sort(key=lambda item: (item.role, item.name))
    return results


def _aggregate_identity(
    digests: Iterable[EvidenceFileDigest],
    *,
    source_commit: str | None,
    contract_fingerprints: Mapping[str, str] | None = None,
) -> str:
    aggregate = hashlib.sha256()
    aggregate.update(f"source_commit={source_commit or ''}\n".encode("utf-8"))
    for key, value in sorted((contract_fingerprints or {}).items()):
        aggregate.update(f"contract:{key}={value}\n".encode("utf-8"))
    for item in digests:
        aggregate.update(item.role.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(item.sha256.encode("ascii"))
        aggregate.update(b"\0")
        aggregate.update(str(item.size_bytes).encode("ascii"))
        aggregate.update(b"\n")
    return aggregate.hexdigest()


def build_reproducibility_manifest(
    files: Iterable[EvidenceFile],
    *,
    source_commit: str | None,
    protocol: str = "morpheus-reproducibility-manifest-v1",
) -> dict[str, object]:
    """Build the backwards-compatible byte-identity manifest.

    This legacy-compatible function intentionally accepts a caller-supplied
    source string because historic non-release research records used abbreviated
    revisions. Release packaging should use
    :func:`build_release_reproducibility_manifest`, which requires an exact Git
    SHA and control-contract fingerprints.
    """

    digests = hash_evidence_files(files)
    return {
        "schema_version": 1,
        "protocol": protocol,
        "source_commit": source_commit,
        "files": [item.as_dict() for item in digests],
        "aggregate_evidence_sha256": _aggregate_identity(digests, source_commit=source_commit),
        "evidence_state": "REPRODUCIBILITY_MANIFEST_NOT_EXTERNAL_ATTESTATION",
        "truth_note": (
            "Hashes preserve byte identity and linkage only. They do not independently validate measurement methodology, "
            "correctness, novelty, authorship, signature authenticity, or benchmark claims."
        ),
    }


def build_release_reproducibility_manifest(
    files: Iterable[EvidenceFile],
    *,
    source_commit: str,
    api_contract_sha256: str,
    feature_registry_sha256: str,
) -> dict[str, object]:
    """Build a strict release provenance identity for code + evidence + policy.

    The two contract fingerprints bind a release record to the API route surface
    and feature-authority policy that governed it. They are local canonical
    digests, not signatures, trusted timestamps, remote attestations, or proof
    that the referenced measurements are scientifically valid.
    """

    source_commit = source_commit.strip().lower()
    api_contract_sha256 = api_contract_sha256.strip().lower()
    feature_registry_sha256 = feature_registry_sha256.strip().lower()
    if not _valid_hex(source_commit, 40):
        raise ValueError("release reproducibility source_commit must be a 40-character hexadecimal Git SHA")
    if not _valid_hex(api_contract_sha256, 64):
        raise ValueError("api_contract_sha256 must be a 64-character hexadecimal SHA-256")
    if not _valid_hex(feature_registry_sha256, 64):
        raise ValueError("feature_registry_sha256 must be a 64-character hexadecimal SHA-256")

    digests = hash_evidence_files(files)
    fingerprints = {
        "api_contract_sha256": api_contract_sha256,
        "feature_registry_sha256": feature_registry_sha256,
    }
    manifest_core = {
        "schema_version": 2,
        "protocol": "morpheus-release-reproducibility-manifest-v2",
        "source_commit": source_commit,
        "contract_fingerprints": fingerprints,
        "files": [item.as_dict() for item in digests],
        "aggregate_evidence_sha256": _aggregate_identity(
            digests,
            source_commit=source_commit,
            contract_fingerprints=fingerprints,
        ),
        "evidence_state": "RELEASE_REPRODUCIBILITY_IDENTITY_NOT_EXTERNAL_ATTESTATION",
        "truth_note": (
            "This binds file hashes, exact source revision, API route-contract identity and feature-policy identity. "
            "It does not independently validate benchmark methodology, signatures, authorship, legal claims, novelty, or external reproducibility."
        ),
    }
    canonical = json.dumps(manifest_core, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return {
        **manifest_core,
        "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
    }
