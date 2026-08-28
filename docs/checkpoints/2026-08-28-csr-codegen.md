# MORPHEUS P3 Checkpoint — Generated CSR Graph Support

Date: 2026-08-28

## Gap closed

The synthesis catalog could select `csr_graph` for `graph_traversal`, and the C++ core already provided deterministic CSR build and BFS traversal, but standalone generated artifacts rejected graph assignments because graph queries intentionally do not require a record field.

## Generated artifact contract

`backend/app/artifact_codegen.py` now treats graph topology as a first-class external input instead of pretending edges are stored in an arbitrary record column.

For each graph-traversal assignment the generated class now contains:

- a `morpheus::CSRGraphIndex<std::uint32_t>` member;
- `configure_graph_<query_index>(node_count, edges, directed)` for explicit topology construction;
- `query_<query_index>(start, max_depth)` returning deterministic BFS order.

Generated headers include `morpheus/csr_graph.hpp` and the standard headers needed for graph edge pairs, depth limits and move semantics.

## State-isolation rule

Graph topology is not part of the record-backed index rebuild path. `insert`, `update_at` and `erase_at` still rebuild record-position indexes for correctness, but they do not reset configured CSR graph members. This mirrors MWS semantics: `graph_traversal` has no mandatory physical record field, so graph topology must remain explicit rather than being silently inferred.

## Verification

`backend/tests/test_graph_codegen.py` synthesizes a graph-only workload, verifies that CSR is selected, generates the C++ artifact, compiles it with the available C++20 compiler and executes behavior checks covering:

- directed graph configuration;
- duplicate-edge deduplication inherited from the CSR primitive;
- deterministic BFS at depth one and depth two;
- preservation of configured topology across ordinary record insert/update/erase rebuilds.

The code and test are committed independently. GitHub Actions run `33149006991` was still in progress when this checkpoint was written, so full CI success is intentionally not claimed here yet.

## Truth boundaries

- Generated CSR support currently targets traversal over an explicitly configured static/read-mostly graph.
- Incremental edge mutation is not claimed; changing topology requires another CSR build.
- Node IDs are currently generated as `std::uint32_t`, matching the core default and keeping the generated API deterministic.
- CI smoke/behavior verification establishes build and semantic correctness for the tested cases, not performance claims.

## Next

1. Close cross-platform CI for graph artifact generation and behavior.
2. Extend generated graph evidence with invalid-node/out-of-range behavior tests.
3. Continue incremental composite record-index maintenance so record mutations no longer require complete index rebuilds where stable row identity makes that safe.
4. Continue P3/P6 closure and then remaining MORPHEUS validation/release work before shifting priority to Butterfly Engine.
