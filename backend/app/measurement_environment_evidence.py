from __future__ import annotations

import json

from .evidence_validation import EvidenceValidation
from .measurement_environment import validate_measurement_environment_record


ROLE = "measurement_environment_record"


def validate_measurement_environment_record_bytes(data: bytes) -> EvidenceValidation:
    try:
        payload = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("measurement environment record is not UTF-8",))
    except json.JSONDecodeError as exc:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (f"invalid JSON: {exc.msg}",))
    if not isinstance(payload, dict):
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("top-level JSON value must be an object",))
    try:
        validate_measurement_environment_record(payload)
    except ValueError as exc:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (str(exc),))
    return EvidenceValidation(
        ROLE,
        True,
        "EVIDENCE_STRUCTURAL_VALIDATION_PASSED",
        ("validated start/end environment snapshot hashes, campaign coverage semantics and record content hash",),
    )
