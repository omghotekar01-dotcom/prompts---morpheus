from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class MigrationReproductionCampaign:
    schema: str
    release_manifest_sha256: str
    receipt_sha256s: tuple[str, ...]
    runner_environment_sha256s: tuple[str, ...]
    result_artifact_sha256s: tuple[str, ...]
    minimum_runs: int
    reproduction_campaign_verified: bool
    campaign_sha256: str


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def promote_generated_migration_reproduction_campaign(*, receipts: Iterable[Any], minimum_runs: int = 3) -> MigrationReproductionCampaign:
    """Promote repeated successful reproductions of one immutable MORPHEUS release.

    Each receipt must independently identify its execution environment, stdout, and
    result artifact.  Receipt order is deliberately irrelevant to campaign identity.
    """
    if isinstance(minimum_runs, bool) or not isinstance(minimum_runs, int) or minimum_runs < 3:
        raise ValueError("minimum_runs must be an exact integer >= 3")

    rows = list(receipts)
    if len(rows) < minimum_runs:
        raise ValueError("insufficient independent reproduction runs")

    release: str | None = None
    receipt_ids: list[str] = []
    environments: list[str] = []
    results: list[str] = []
    stdout_ids: list[str] = []

    for index, receipt in enumerate(rows):
        if getattr(receipt, "reproduction_verified", None) is not True:
            raise ValueError(f"receipt {index} is not explicitly reproduction-verified")
        receipt_id = _hash(getattr(receipt, "receipt_sha256", None), f"receipts[{index}].receipt_sha256")
        release_id = _hash(getattr(receipt, "release_manifest_sha256", None), f"receipts[{index}].release_manifest_sha256")
        environment = _hash(getattr(receipt, "runner_environment_sha256", None), f"receipts[{index}].runner_environment_sha256")
        stdout = _hash(getattr(receipt, "stdout_artifact_sha256", None), f"receipts[{index}].stdout_artifact_sha256")
        result = _hash(getattr(receipt, "result_artifact_sha256", None), f"receipts[{index}].result_artifact_sha256")
        if release is None:
            release = release_id
        elif release_id != release:
            raise ValueError("all reproduction receipts must target the same release manifest")
        if receipt_id in {release_id, environment, stdout, result}:
            raise ValueError("receipt identity must be independent of upstream evidence identities")
        receipt_ids.append(receipt_id)
        environments.append(environment)
        stdout_ids.append(stdout)
        results.append(result)

    assert release is not None
    if len(set(receipt_ids)) != len(receipt_ids):
        raise ValueError("reproduction receipt identities must be unique")
    if len(set(environments)) != len(environments):
        raise ValueError("runner environment identities must be independent across runs")
    if len(set(stdout_ids)) != len(stdout_ids):
        raise ValueError("stdout evidence must be independent across runs")
    if len(set(results)) != len(results):
        raise ValueError("result artifacts must be independent across runs")

    payload = {
        "schema": "morpheus.generated_migration_reproduction_campaign.v1",
        "release_manifest_sha256": release,
        "receipt_sha256s": sorted(receipt_ids),
        "runner_environment_sha256s": sorted(environments),
        "result_artifact_sha256s": sorted(results),
        "minimum_runs": minimum_runs,
        "reproduction_campaign_verified": True,
    }
    return MigrationReproductionCampaign(
        schema=payload["schema"],
        release_manifest_sha256=release,
        receipt_sha256s=tuple(payload["receipt_sha256s"]),
        runner_environment_sha256s=tuple(payload["runner_environment_sha256s"]),
        result_artifact_sha256s=tuple(payload["result_artifact_sha256s"]),
        minimum_runs=minimum_runs,
        reproduction_campaign_verified=True,
        campaign_sha256=_canonical_sha256(payload),
    )
