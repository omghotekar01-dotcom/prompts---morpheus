from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class MigrationReleaseManifest:
    schema: str
    release_id: str
    publication_bundle_sha256: str
    code_commit_sha256: str
    dataset_archive_sha256: str
    environment_lock_sha256: str
    reproducibility_command_sha256: str
    supporting_artifact_sha256: tuple[str, ...]
    release_ready: bool
    manifest_sha256: str


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_generated_migration_release_manifest(
    *,
    release_id: str,
    publication_bundle_sha256: str,
    publication_ready: bool,
    code_commit_sha256: str,
    dataset_archive_sha256: str,
    environment_lock_sha256: str,
    reproducibility_command_sha256: str,
    supporting_artifact_sha256: Sequence[str],
    active_revocation_count: int,
) -> MigrationReleaseManifest:
    """Bind publication evidence to immutable code/data/environment release inputs.

    This is deliberately a release-readiness record, not proof that a paper result is
    scientifically correct. It prevents a reviewed evidence bundle from being paired
    with substituted code, data, or an environment after review.
    """
    if not isinstance(release_id, str) or not _RELEASE_ID.fullmatch(release_id):
        raise ValueError("release_id must be a canonical 1-128 character identifier")
    if publication_ready is not True:
        raise ValueError("publication bundle must be explicitly ready")
    if isinstance(active_revocation_count, bool) or not isinstance(active_revocation_count, int) or active_revocation_count < 0:
        raise ValueError("active_revocation_count must be a non-negative exact integer")
    if active_revocation_count != 0:
        raise ValueError("release cannot be created while publication evidence is revoked")

    bundle = _hash(publication_bundle_sha256, "publication_bundle_sha256")
    code = _hash(code_commit_sha256, "code_commit_sha256")
    dataset = _hash(dataset_archive_sha256, "dataset_archive_sha256")
    environment = _hash(environment_lock_sha256, "environment_lock_sha256")
    command = _hash(reproducibility_command_sha256, "reproducibility_command_sha256")

    if not isinstance(supporting_artifact_sha256, Sequence) or isinstance(
        supporting_artifact_sha256, (str, bytes, bytearray)
    ):
        raise ValueError("supporting_artifact_sha256 must be a sequence")
    supporting = tuple(sorted(_hash(value, "supporting_artifact_sha256[]") for value in supporting_artifact_sha256))
    if len(set(supporting)) != len(supporting):
        raise ValueError("duplicate supporting artifact identity")

    required = [bundle, code, dataset, environment, command]
    if len(set(required)) != len(required):
        raise ValueError("release evidence identities must be independent")
    if set(supporting) & set(required):
        raise ValueError("supporting artifacts must be independent from required release evidence")

    payload = {
        "schema": "morpheus.generated_migration_release_manifest.v1",
        "release_id": release_id,
        "publication_bundle_sha256": bundle,
        "code_commit_sha256": code,
        "dataset_archive_sha256": dataset,
        "environment_lock_sha256": environment,
        "reproducibility_command_sha256": command,
        "supporting_artifact_sha256": list(supporting),
        "active_revocation_count": 0,
        "release_ready": True,
    }
    return MigrationReleaseManifest(
        schema=payload["schema"],
        release_id=release_id,
        publication_bundle_sha256=bundle,
        code_commit_sha256=code,
        dataset_archive_sha256=dataset,
        environment_lock_sha256=environment,
        reproducibility_command_sha256=command,
        supporting_artifact_sha256=supporting,
        release_ready=True,
        manifest_sha256=_canonical_sha256(payload),
    )
