from __future__ import annotations

from .models import PrimitiveSpec, QueryKind


PRIMITIVES: dict[str, PrimitiveSpec] = {
    "robin_hood_hash": PrimitiveSpec(
        name="robin_hood_hash",
        display_name="Robin Hood Hash Index",
        implementation_id="morpheus.RobinHoodHashIndex.v1",
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
        notes="Fast exact-match index; unordered; model values are bootstrap priors until matching implementation calibration is present.",
    ),
    "sorted_array": PrimitiveSpec(
        name="sorted_array",
        display_name="Mutable Sorted Array Index",
        implementation_id="morpheus.MutableSortedArrayIndex.v1",
        capabilities={QueryKind.POINT_LOOKUP, QueryKind.RANGE_SCAN},
        base_latency_us={QueryKind.POINT_LOOKUP: 0.28, QueryKind.RANGE_SCAN: 0.24},
        memory_bytes_per_record=20.0,
        build_ns_per_record=115.0,
        update_latency_us=8.0,
        notes="Cache-local ordered structure used by generated artifacts; expensive incremental insertion/update. Calibration must target this mutable implementation rather than the legacy bulk-only lab index.",
    ),
    "ordered_tree": PrimitiveSpec(
        name="ordered_tree",
        display_name="B+ Tree Index",
        implementation_id="morpheus.BPlusTreeIndex.rebalanced.v1",
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
            "OrderedTreeIndex remains only as an explicit benchmark/migration baseline."
        ),
    ),
    "radix_trie": PrimitiveSpec(
        name="radix_trie",
        display_name="Mutable Multi-Prefix Trie",
        implementation_id="morpheus.MutableMultiPrefixTrie.v1",
        capabilities={QueryKind.PREFIX_SEARCH, QueryKind.POINT_LOOKUP},
        base_latency_us={QueryKind.PREFIX_SEARCH: 0.22, QueryKind.POINT_LOOKUP: 0.31},
        memory_bytes_per_record=46.0,
        build_ns_per_record=145.0,
        update_latency_us=0.75,
        notes="Duplicate-preserving string/prefix adapter used by generated artifacts; type compatibility is checked by the engine.",
    ),
    "bitmap": PrimitiveSpec(
        name="bitmap",
        display_name="Adaptive Compressed Bitmap Filter Index",
        implementation_id="morpheus.CompressedBitmapFilterIndex.adaptive32.v1",
        capabilities={QueryKind.FILTER},
        base_latency_us={QueryKind.FILTER: 0.11},
        memory_bytes_per_record=2.5,
        build_ns_per_record=36.0,
        update_latency_us=0.24,
        notes=(
            "Partitioned adaptive sparse-array/dense-bitset bitmap with deterministic promotion/demotion hysteresis. "
            "Generated artifacts use 32-bit stable-slot postings with an explicit overflow guard; thresholds remain "
            "engineering defaults until controlled crossover measurements justify tuning."
        ),
    ),
    "csr_graph": PrimitiveSpec(
        name="csr_graph",
        display_name="CSR Graph",
        implementation_id="morpheus.CSRGraphIndex.v1",
        capabilities={QueryKind.GRAPH_TRAVERSAL},
        base_latency_us={QueryKind.GRAPH_TRAVERSAL: 0.42},
        memory_bytes_per_record=16.0,
        build_ns_per_record=125.0,
        update_latency_us=50.0,
        notes=(
            "Read-optimized deterministic CSR graph with sorted/deduplicated adjacency and BFS traversal. "
            "Generated artifacts expose explicit graph-topology configuration plus traversal queries; topology is "
            "kept separate from ordinary record fields and is rebuild-heavy for dynamic edge mutation."
        ),
    ),
}


def compatible_primitives(kind: QueryKind) -> list[PrimitiveSpec]:
    return [primitive for primitive in PRIMITIVES.values() if kind in primitive.capabilities]
