from __future__ import annotations

import json

from .evidence_validation import EvidenceValidation, validate_evidence_bytes
from .generated_migration_evidence import ROLE as GENERATED_MIGRATION_ROLE
from .generated_migration_evidence import validate_generated_migration_manifest_bytes
from .generated_migration_release_evidence import validate_generated_migration_evidence_bytes
from .machine_profile import MACHINE_PROFILE_PROTOCOL


_RQ7_ROLES = {
    "generated_migration_campaign",
    "generated_migration_campaign_summary",
}


def _looks_like_machine_profile_v2(data: bytes) -> bool:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("protocol") == MACHINE_PROFILE_PROTOCOL


def validate_release_evidence_bytes(role: str, data: bytes) -> EvidenceValidation:
    """Validate a release artifact with strict role-specific dispatch.

    New high-risk evidence roles are handled explicitly here rather than falling
    through the generic JSON-acceptance path. Existing roles preserve the mature
    validator contract. Machine-profile v2 is dispatched only when its protocol
    is actually present, so older v1 release evidence remains backward compatible.
    """

    normalized = role.strip()
    if normalized == GENERATED_MIGRATION_ROLE:
        return validate_generated_migration_manifest_bytes(data)
    if normalized in _RQ7_ROLES or (normalized == "machine_profile" and _looks_like_machine_profile_v2(data)):
        try:
            _payload, details = validate_generated_migration_evidence_bytes(normalized, data)
        except ValueError as exc:
            return EvidenceValidation(
                normalized,
                False,
                "EVIDENCE_STRUCTURAL_VALIDATION_FAILED",
                (str(exc),),
            )
        return EvidenceValidation(
            normalized,
            True,
            "EVIDENCE_STRUCTURAL_VALIDATION_PASSED",
            details,
        )
    return validate_evidence_bytes(normalized, data)
