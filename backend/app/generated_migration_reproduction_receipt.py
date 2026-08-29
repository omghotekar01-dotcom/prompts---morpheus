from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class MigrationReproductionReceipt:
    schema: str
    run_id: str
    release_manifest_sha256: str
    runner_environment_sha256: str
    stdout_artifact_sha256: str
    result_artifact_sha256: str
    exit_code: int
    assertions_passed: int
    reproduction_verified: bool
    receipt_sha256: str


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def build_generated_migration_reproduction_receipt(*, run_id: str, release_manifest_sha256: str,
    release_ready: bool, runner_environment_sha256: str, stdout_artifact_sha256: str,
    result_artifact_sha256: str, exit_code: int, assertions_passed: int) -> MigrationReproductionReceipt:
    """Record an actual successful reproduction attempt against one immutable release manifest."""
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise ValueError("run_id must be a canonical 1-128 character identifier")
    if release_ready is not True:
        raise ValueError("release manifest must be explicitly ready")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise ValueError("exit_code must be an exact integer")
    if exit_code != 0:
        raise ValueError("reproduction process must exit successfully")
    if isinstance(assertions_passed, bool) or not isinstance(assertions_passed, int) or assertions_passed <= 0:
        raise ValueError("assertions_passed must be a positive exact integer")

    release = _hash(release_manifest_sha256, "release_manifest_sha256")
    environment = _hash(runner_environment_sha256, "runner_environment_sha256")
    stdout = _hash(stdout_artifact_sha256, "stdout_artifact_sha256")
    result = _hash(result_artifact_sha256, "result_artifact_sha256")
    identities = [release, environment, stdout, result]
    if len(set(identities)) != len(identities):
        raise ValueError("reproduction evidence identities must be independent")

    payload = {
        "schema": "morpheus.generated_migration_reproduction_receipt.v1",
        "run_id": run_id,
        "release_manifest_sha256": release,
        "runner_environment_sha256": environment,
        "stdout_artifact_sha256": stdout,
        "result_artifact_sha256": result,
        "exit_code": 0,
        "assertions_passed": assertions_passed,
        "reproduction_verified": True,
    }
    return MigrationReproductionReceipt(**payload, receipt_sha256=_canonical_sha256(payload))
