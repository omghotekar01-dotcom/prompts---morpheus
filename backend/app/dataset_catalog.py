from __future__ import annotations

"""Explain the real compiled-primitive inventory and per-query compatibility."""

from .catalog import PRIMITIVES
from .engine import _primitive_compatible_with_query
from .models import QuerySpec, WorkloadSpec
from .primitive_manifest import _IMPLEMENTATION_PATHS


def catalog_inventory() -> list[dict]:
    return [
        {
            "id": p.name,
            "name": p.display_name,
            "implementation_id": p.implementation_id,
            "source_path": _IMPLEMENTATION_PATHS.get(p.name),
            "operations": sorted(kind.value for kind in p.capabilities),
            "bootstrap_memory_bytes_per_record": p.memory_bytes_per_record,
            "evidence": "CATALOG_PRIOR_NOT_A_DATASET_BENCHMARK",
            "notes": p.notes,
        }
        for p in sorted(PRIMITIVES.values(), key=lambda value: value.name)
    ]


def query_options(spec: WorkloadSpec) -> list[dict]:
    result = []
    for index, query in enumerate(spec.queries):
        choices = []
        for p in sorted(PRIMITIVES.values(), key=lambda value: value.name):
            reason = None
            if query.kind not in p.capabilities:
                reason = f"{p.display_name} does not implement {query.kind.value}"
            elif not _primitive_compatible_with_query(spec, query, p.name):
                if p.name == "radix_trie":
                    reason = "Prefix trie requires a string/text column"
                elif p.name == "bitmap":
                    reason = "Bitmap is excluded for very high-cardinality fields"
                else:
                    reason = "Incompatible with this column's type/cardinality"
            choices.append({
                "primitive": p.name,
                "display_name": p.display_name,
                "eligible": reason is None,
                "reason": reason,
                "implementation_id": p.implementation_id,
            })
        result.append({
            "query_index": index,
            "kind": query.kind.value,
            "field": query.field,
            "choices": choices,
        })
    return result
