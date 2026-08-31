from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .pilot_readiness import SCHEMA


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_CHECK_FIELDS = {"id", "required", "passed", "detail", "evidence_state"}


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_pilot_readiness(report: Mapping[str, Any]) -> bool:
    """Fail closed unless a pilot-readiness receipt is internally consistent.

    This verifies only the deterministic structure and digest of a readiness
    receipt. It does not independently re-run the operational checks and cannot
    promote a single-node pilot into production authorization or certification.
    """

    try:
        if report.get("schema") != SCHEMA:
            return False
        digest = report.get("readiness_sha256")
        if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
            return False

        ready = report.get("ready")
        if type(ready) is not bool:
            return False
        state = report.get("state")
        if state not in {"PILOT_READY_SINGLE_NODE_SCOPE", "PILOT_NOT_READY"}:
            return False

        checks = report.get("checks")
        if not isinstance(checks, list) or not checks:
            return False

        check_ids: list[str] = []
        derived_blockers: list[str] = []
        derived_advisories: list[str] = []
        for item in checks:
            if not isinstance(item, Mapping) or not _REQUIRED_CHECK_FIELDS <= set(item):
                return False
            check_id = item.get("id")
            required = item.get("required")
            passed = item.get("passed")
            detail = item.get("detail")
            evidence_state = item.get("evidence_state")
            if not isinstance(check_id, str) or not check_id:
                return False
            if type(required) is not bool or type(passed) is not bool:
                return False
            if not isinstance(detail, str) or not detail:
                return False
            if not isinstance(evidence_state, str) or not evidence_state:
                return False
            check_ids.append(check_id)
            if not passed:
                (derived_blockers if required else derived_advisories).append(check_id)

        if len(check_ids) != len(set(check_ids)):
            return False
        if report.get("blockers") != derived_blockers:
            return False
        if report.get("advisories") != derived_advisories:
            return False
        if ready is not (not derived_blockers):
            return False
        expected_state = "PILOT_READY_SINGLE_NODE_SCOPE" if ready else "PILOT_NOT_READY"
        if state != expected_state:
            return False

        scope = report.get("scope")
        if not isinstance(scope, Mapping):
            return False
        if scope.get("deployment_shape") != "SINGLE_NODE_LOCAL_CONTROL_PLANE":
            return False

        truth_boundaries = report.get("truth_boundaries")
        if not isinstance(truth_boundaries, list) or not truth_boundaries:
            return False
        if any(not isinstance(item, str) or not item for item in truth_boundaries):
            return False

        core = dict(report)
        core.pop("readiness_sha256", None)
        return _canonical_sha256(core) == digest
    except (TypeError, ValueError):
        return False
