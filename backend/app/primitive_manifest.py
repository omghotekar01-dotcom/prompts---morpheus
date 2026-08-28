from __future__ import annotations

import hashlib
import json
from typing import Any

from .catalog import PRIMITIVES


PRIMITIVE_MANIFEST_VERSION = "morpheus-primitive-manifest-v2"

_IMPLEMENTATION_PATHS = {
    "robin_hood_hash": "core/include/morpheus/structures.hpp",
    "sorted_array": "core/include/morpheus/mutable_indices.hpp",
    "ordered_tree": "core/include/morpheus/bplus_tree.hpp",
    "radix_trie": "core/include/morpheus/mutable_indices.hpp",
    "bitmap": "core/include/morpheus/compressed_bitmap.hpp",
    "csr_graph": "core/include/morpheus/csr_graph.hpp",
}


def primitive_manifest_dict() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for name in sorted(PRIMITIVES):
        primitive = PRIMITIVES[name]
        entries.append(
            {
                "name": primitive.name,
                "display_name": primitive.display_name,
                "implementation_id": primitive.implementation_id,
                "capabilities": sorted(item.value for item in primitive.capabilities),
                "bootstrap_latency_us": {
                    kind.value: primitive.base_latency_us[kind]
                    for kind in sorted(primitive.base_latency_us, key=lambda item: item.value)
                },
                "bootstrap_memory_bytes_per_record": primitive.memory_bytes_per_record,
                "bootstrap_build_ns_per_record": primitive.build_ns_per_record,
                "bootstrap_update_latency_us": primitive.update_latency_us,
                "implementation_path": _IMPLEMENTATION_PATHS.get(name),
                "notes": primitive.notes,
            }
        )
    return {
        "schema": PRIMITIVE_MANIFEST_VERSION,
        "entries": entries,
        "truth_boundary": (
            "Catalog costs are bootstrap priors unless an active measurement matches both primitive name and physical implementation_id. "
            "Implementation paths identify repository source locations; exact bytes are bound by the Git/release commit."
        ),
    }


def canonical_primitive_manifest_json() -> str:
    return json.dumps(
        primitive_manifest_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def primitive_manifest_hash() -> str:
    return hashlib.sha256(canonical_primitive_manifest_json().encode("utf-8")).hexdigest()
