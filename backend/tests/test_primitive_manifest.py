from __future__ import annotations

import hashlib
import json

from app.catalog import PRIMITIVES
from app.primitive_manifest import (
    PRIMITIVE_MANIFEST_VERSION,
    canonical_primitive_manifest_json,
    primitive_manifest_dict,
    primitive_manifest_hash,
)


def test_primitive_manifest_is_deterministic_complete_and_canonical() -> None:
    first = primitive_manifest_dict()
    second = primitive_manifest_dict()
    assert first == second
    assert first["schema"] == PRIMITIVE_MANIFEST_VERSION
    assert PRIMITIVE_MANIFEST_VERSION == "morpheus-primitive-manifest-v2"
    assert [entry["name"] for entry in first["entries"]] == sorted(PRIMITIVES)
    assert len(first["entries"]) == len(PRIMITIVES)
    assert len(primitive_manifest_hash()) == 64
    assert json.loads(canonical_primitive_manifest_json()) == first

    for entry in first["entries"]:
        assert entry["capabilities"] == sorted(entry["capabilities"])
        assert entry["implementation_id"] == PRIMITIVES[entry["name"]].implementation_id
        assert entry["implementation_id"].startswith("morpheus.")
        assert entry["implementation_path"].startswith("core/include/morpheus/")
        assert entry["bootstrap_memory_bytes_per_record"] > 0
        assert "bootstrap" in first["truth_boundary"].lower()
        assert "implementation_id" in first["truth_boundary"]


def test_manifest_hash_changes_if_catalog_semantics_change_without_mutating_catalog() -> None:
    original = primitive_manifest_hash()
    payload = primitive_manifest_dict()
    payload["entries"][0]["bootstrap_memory_bytes_per_record"] += 1
    changed = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(changed.encode("utf-8")).hexdigest() != original


def test_manifest_hash_changes_if_physical_implementation_identity_changes() -> None:
    original = primitive_manifest_hash()
    payload = primitive_manifest_dict()
    payload["entries"][0]["implementation_id"] += ".different"
    changed = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(changed.encode("utf-8")).hexdigest() != original
