from __future__ import annotations

from .evidence_validation import EvidenceValidation, validate_evidence_bytes
from .generated_migration_evidence import ROLE as GENERATED_MIGRATION_ROLE
from .generated_migration_evidence import validate_generated_migration_manifest_bytes


def validate_release_evidence_bytes(role: str, data: bytes) -> EvidenceValidation:
    """Validate a release artifact with strict role-specific dispatch.

    New high-risk evidence roles are handled explicitly here rather than falling
    through the generic JSON-acceptance path. Existing roles preserve the mature
    validator contract.
    """

    normalized = role.strip()
    if normalized == GENERATED_MIGRATION_ROLE:
        return validate_generated_migration_manifest_bytes(data)
    return validate_evidence_bytes(normalized, data)
