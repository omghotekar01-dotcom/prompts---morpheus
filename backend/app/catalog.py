from __future__ import annotations

from .models import PrimitiveSpec, QueryKind


PRIMITIVES: dict[str, PrimitiveSpec] = {
    "robin_hood_hash": PrimitiveSpec(
        name="robin_hood_hash",
        display_name="Robin Hood Hash Index",
        capabilities={QueryKind.POINT_LOOKUP, QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE},
        base_latency_us={
            QueryKind.POINT_LOOKUP: 0.09,
            QueryKind.INSERT: 0.16,
            QueryKind.UPDATE: 0.17,
            QueryKind.DELETE: 0.18,
        },
        memory_bytes_per_record=36.0,
        build_ns_per_record=52.0,
        update_latency_us=0.17,
        notes="Fast exact-match index; unordered; model values are bootstrap priors until calibrated.",
    ),
    "sorted_array": PrimitiveSpec(
        name="sorted_array",
        display_name="Sorted Array Index",
        capabilities={QueryKind.POINT_LOOKUP, QueryKind.RANGE_SCAN},
        base_latency_us={QueryKind.POINT_LOOKUP: 0.28, QueryKind.RANGE_SCAN: 0.24},
        memory_bytes_per_record=20.0,
        build_ns_per_record=115.0,
        update_latency_us=8.0,
        notes="Excellent cache locality for read-mostly ordered workloads; expensive updates.",
    ),
    "ordered_tree": PrimitiveSpec(
        name="ordered_tree",
        display_name="B+ Tree Index",
        capabilities={
            QueryKind.POINT_LOOKUP,
            QueryKind.RANGE_SCAN,
            QueryKind.INSERT,
            QueryKind.UPDATE,
            QueryKind.DELETE,
        },
        base_latency_us={
            QueryKind.POINT_LOOKUP: 0.45,
            QueryKind.RANGE_SCAN: 0.35,
            QueryKind.INSERT: 0.62,
            QueryKind.UPDATE: 0.68,
            QueryKind.DELETE: 0.73,
        },
        memory_bytes_per_record=52.0,
        build_ns_per_record=180.0,
        update_latency_us=0.68,
        notes=(
            "Linked-leaf B+ tree with incremental leaf/internal borrow+merge deletion and root collapse. "
            "Generated ordered-index artifacts use the rebalancing BPlusTreeIndex; the legacy rebuild-based "
            "OrderedTreeIndex remains only as an explicit benchmark/migration baseline. Cost numbers remain "
            "bootstrap priors until controlled calibration is rerun for the new implementation."
        ),
    ),
    "radix_trie": PrimitiveSpec(
        name="radix_trie",
        display_name="Radix Trie",
        capabilities={QueryKind.PREFIX_SEARCH, QueryKind.POINT_LOOKUP},
        base_latency_us={QueryKind.PREFIX_SEARCH: 0.22, QueryKind.POINT_LOOKUP: 0.31},
        memory_bytes_per_record=46.0,
        build_ns_per_record=145.0,
        update_latency_us=0.75,
        notes="String/prefix-oriented index; type compatibility is checked by the engine.",
    ),
    "bitmap": PrimitiveSpec(
        name="bitmap",
        display_name="Bitmap Filter Index",
        capabilities={QueryKind.FILTER},
        base_latency_us={QueryKind.FILTER: 0.11},
        memory_bytes_per_record=2.5,
        build_ns_per_record=36.0,
        update_latency_us=0.24,
        notes=(
            "Partitioned adaptive sparse-array/dense-bitset bitmap with deterministic promotion/demotion hysteresis. "
            "Thresholds remain engineering defaults until controlled crossover measurements justify tuning; "
            "run-container and wire-compatible Roaring support remain open."
        ),
    ),
    "csr_graph": PrimitiveSpec(
        name="csr_graph",
        display_name="CSR Graph",
        capabilities={QueryKind.GRAPH_TRAVERSAL},
        base_latency_us={QueryKind.GRAPH_TRAVERSAL: 0.42},
        memory_bytes_per_record=16.0,
        build_ns_per_record=125.0,
        update_latency_us=50.0,
        notes="Read-optimized sparse graph representation; rebuild-heavy for dynamic graphs; generated artifact support is not yet implemented.",
    ),
}


def compatible_primitives(kind: QueryKind) -> list[PrimitiveSpec]:
    return [primitive for primitive in PRIMITIVES.values() if kind in primitive.capabilities]
