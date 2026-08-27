from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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


def build_reproducibility_manifest(
    files: Iterable[EvidenceFile],
    *,
    source_commit: str | None,
    protocol: str = "morpheus-reproducibility-manifest-v1",
) -> dict[str, object]:
    digests = hash_evidence_files(files)
    aggregate = hashlib.sha256()
    for item in digests:
        aggregate.update(item.role.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(item.sha256.encode("ascii"))
        aggregate.update(b"\0")
        aggregate.update(str(item.size_bytes).encode("ascii"))
        aggregate.update(b"\n")

    return {
        "schema_version": 1,
        "protocol": protocol,
        "source_commit": source_commit,
        "files": [item.as_dict() for item in digests],
        "aggregate_evidence_sha256": aggregate.hexdigest(),
        "evidence_state": "REPRODUCIBILITY_MANIFEST_NOT_EXTERNAL_ATTESTATION",
        "truth_note": (
            "Hashes preserve byte identity and linkage only. They do not independently validate measurement methodology, "
            "correctness, novelty, authorship, signature authenticity, or benchmark claims."
        ),
    }
