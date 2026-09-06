from __future__ import annotations

import hashlib
import json

from .artifact_codegen import CPP_TYPES
from .models import WorkloadSpec


GENERATED_RECORD_SCHEMA_PREFIX = "morpheus-record-schema-v1:"


def _normalized_cpp_type(raw_type: str) -> str:
    """Match the generated Record field-type normalization used by codegen."""

    return CPP_TYPES.get(raw_type.lower(), "std::string")


def generated_record_schema_identity(spec: WorkloadSpec) -> str:
    """Return a deterministic compatibility identity for a generated Record schema.

    The identity intentionally depends only on ordered logical field names and the
    normalized C++ field types emitted by artifact codegen. It does not depend on
    workload name, candidate id, namespace, query mix, physical primitives, cost
    estimates, or benchmark evidence, so physically different generated indexes
    can exchange logical snapshots when they expose the same Record contract.

    This SHA-256 value is a deterministic content/compatibility fingerprint. It is
    not a signature, authentication mechanism, trusted timestamp, freshness proof,
    or authorization to restore or activate an artifact.
    """

    payload = {
        "schema": "morpheus.generated-record",
        "version": 1,
        "fields": [
            {
                "name": field.name,
                "cpp_type": _normalized_cpp_type(field.type),
            }
            for field in spec.fields
        ],
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return GENERATED_RECORD_SCHEMA_PREFIX + hashlib.sha256(canonical).hexdigest()
