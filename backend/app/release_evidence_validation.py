from __future__ import annotations

import json

from .evidence_validation import EvidenceValidation, validate_evidence_bytes
from .generated_migration_evidence import ROLE as GENERATED_MIGRATION_ROLE
from .generated_migration_evidence import validate_generated_migration_manifest_bytes
from .generated_migration_release_evidence import validate_generated_migration_evidence_bytes
from .generated_migration_transition_evidence import ROLE as GENERATED_MIGRATION_TRANSITION_ROLE
from .generated_migration_transition_evidence import validate_generated_migration_transition_cost_evidence_bytes
from .machine_profile import MACHINE_PROFILE_PROTOCOL
from .measurement_environment_evidence import ROLE as MEASUREMENT_ENVIRONMENT_ROLE
from .measurement_environment_evidence import validate_measurement_environment_record_bytes
from .rq7_analysis_provenance import (
    PROVENANCE_ROLE as RQ7_ANALYSIS_PROVENANCE_ROLE,
    SOURCE_ROLE as RQ7_ANALYSIS_SOURCE_ROLE,
    validate_rq7_analysis_provenance_bytes,
    validate_rq7_analysis_source_bytes,
)
from .rq7_confirmatory_evidence import ROLE as RQ7_CONFIRMATORY_ROLE
from .rq7_confirmatory_evidence import validate_rq7_confirmatory_analysis_bytes
from .rq7_record_count_effect_evidence import ROLE as RQ7_RECORD_COUNT_EFFECT_ROLE
from .rq7_record_count_effect_evidence import validate_rq7_record_count_effect_evidence_bytes


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
    """Validate a release artifact with strict role-specific dispatch."""

    normalized = role.strip()
    if normalized == GENERATED_MIGRATION_ROLE:
        return validate_generated_migration_manifest_bytes(data)
    if normalized == GENERATED_MIGRATION_TRANSITION_ROLE:
        return validate_generated_migration_transition_cost_evidence_bytes(data)
    if normalized == RQ7_CONFIRMATORY_ROLE:
        return validate_rq7_confirmatory_analysis_bytes(data)
    if normalized == MEASUREMENT_ENVIRONMENT_ROLE:
        return validate_measurement_environment_record_bytes(data)
    if normalized == RQ7_ANALYSIS_SOURCE_ROLE:
        return validate_rq7_analysis_source_bytes(data)
    if normalized == RQ7_ANALYSIS_PROVENANCE_ROLE:
        return validate_rq7_analysis_provenance_bytes(data)
    if normalized == RQ7_RECORD_COUNT_EFFECT_ROLE:
        return validate_rq7_record_count_effect_evidence_bytes(data)
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
        return EvidenceValidation(normalized, True, "EVIDENCE_STRUCTURAL_VALIDATION_PASSED", details)
    return validate_evidence_bytes(normalized, data)
