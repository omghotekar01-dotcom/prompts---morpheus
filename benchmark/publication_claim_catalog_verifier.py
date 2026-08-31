"""Independent verifier for serialized MORPHEUS publication claim catalogs."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_SCHEMA = "morpheus.publication_claim_catalog.v1"
_REQUIRED = {
    "schema", "source_revision", "manifest_count", "claim_count",
    "manifest_sha256", "claims", "catalog_sha256",
    "publication_claims_authorized", "production_deployment_authorized",
}


def _digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_publication_claim_catalog(catalog: Mapping[str, Any]) -> str:
    """Verify a plain serialized catalog without trusting the producer-side builder."""
    if not isinstance(catalog, Mapping):
        raise ValueError("catalog must be a mapping")
    if set(catalog) != _REQUIRED:
        raise ValueError("catalog fields do not match the closed schema")
    if catalog["schema"] != _SCHEMA:
        raise ValueError("unsupported catalog schema")

    revision = catalog["source_revision"]
    if not isinstance(revision, str) or not _HEX40.fullmatch(revision):
        raise ValueError("source_revision must be a lowercase 40-hex Git revision")

    manifests = catalog["manifest_sha256"]
    claims = catalog["claims"]
    if not isinstance(manifests, list) or not manifests:
        raise ValueError("manifest_sha256 must be a non-empty list")
    if any(not isinstance(value, str) or not _HEX64.fullmatch(value) for value in manifests):
        raise ValueError("manifest_sha256 entries must be lowercase SHA-256 values")
    if manifests != sorted(manifests) or len(set(manifests)) != len(manifests):
        raise ValueError("manifest identities must be unique and canonically ordered")

    if not isinstance(claims, list) or not claims:
        raise ValueError("claims must be a non-empty list")
    if any(not isinstance(value, str) or not value.strip() or value != value.strip() for value in claims):
        raise ValueError("claims must be trimmed non-empty strings")
    if claims != sorted(claims, key=str.casefold):
        raise ValueError("claims are not canonically ordered")
    if len({value.casefold() for value in claims}) != len(claims):
        raise ValueError("duplicate publication claims are not allowed")

    for field, expected in (("manifest_count", len(manifests)), ("claim_count", len(claims))):
        value = catalog[field]
        if isinstance(value, bool) or not isinstance(value, int) or value != expected:
            raise ValueError(f"{field} does not match serialized evidence")

    if catalog["publication_claims_authorized"] is not True:
        raise ValueError("publication claims are not authorized")
    if catalog["production_deployment_authorized"] is not False:
        raise ValueError("production deployment authority is forbidden")

    payload = {
        "schema": _SCHEMA,
        "source_revision": revision,
        "manifest_sha256": manifests,
        "claims": claims,
        "publication_claims_authorized": True,
        "production_deployment_authorized": False,
    }
    expected = _digest(payload)
    supplied = catalog["catalog_sha256"]
    if not isinstance(supplied, str) or not _HEX64.fullmatch(supplied) or supplied != expected:
        raise ValueError("catalog digest mismatch")
    return expected
