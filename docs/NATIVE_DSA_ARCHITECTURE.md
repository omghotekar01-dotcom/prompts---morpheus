# MORPHEUS: Native DSA architecture and evidence boundaries

**Owner/commit attribution requested:** Om Ghotekar <omghotekar01@gmail.com>
**Migration label:** Homebot native-DSA track

## Purpose

MORPHEUS takes a typed **workload** (operation kinds, field types, traffic
weights, selectivity, estimated scale and hard limits) and searches for a
compatible **combination** of data structures. A different workload is allowed
to produce a different result. There is no rule like "if the user types X,
return structure Y". No external generative AI is required for selection.

The system is an optimizer, not a promise to find a universally fastest
structure. A recommendation is optimal **only within the evaluated candidate
space, search strategy, modeled objective and hard constraints**. Empirical
claims require actual compiled-artifact benchmarks, distribution-aligned
calibration, repetitions and comparison to declared baselines.

## Architecture: implemented

1. **C++20 DSA core** — actual hash, B+ tree, sorted-array, trie, bitmap and
   CSR implementations in `core/include/morpheus/`, native search in
   `native_search.hpp`, and compiled `morpheus_native_search` CLI.
   The native search performs exhaustive enumeration, bounded beam search and
   deterministic greedy search on **request-supplied** option estimates.
   There is no workload-specific answer table.
2. **Python API adapter (remaining migration boundary)** — FastAPI parses
   MWS YAML/JSON, checks fields/constraints, identifies currently compatible
   implementations, resolves calibration-backed or bootstrap cost estimates,
   invokes C++20 through a bounded subprocess with no shell, and validates
   the response. Existing Python evaluation and artifact preview code are
   temporarily retained for API compatibility. This is **not yet** an
   exclusively C++ implementation of all business logic.
3. **React frontend** — collects real MWS inputs and displays candidate
   outcomes, cost provenance and verification. Bundled example workloads are
   templates only. They must not be represented as measurements of user data.
4. **Evidence** — cost predictions and synthetic examples remain labeled
   accordingly. Actual speed and correctness require generated C++ compile,
   differential testing, and real benchmarks. Failing those checks must not
   be called "verified" or "best measured".

## Native search selection policy

- The packaged Docker runtime builds the native C++20 executable and requires
  it for synthesis. The Windows one-click launcher compiles the executable with
  CMake and requires it before starting the API.
- `MORPHEUS_SEARCH_BACKEND=native`: compiled search required, failures surfaced.
- `MORPHEUS_SEARCH_BACKEND=auto` (developer/default): compiled search preferred,
  legacy Python search used only when native binary is unavailable. A warning
  is included in synthesis output when the fallback occurs.
- `MORPHEUS_SEARCH_BACKEND=python`: explicit legacy compatibility/research mode.
- `MORPHEUS_NATIVE_SEARCH_EXECUTABLE` selects an exact executable path.
- Native protocol is `MORPHEUS_NATIVE_SEARCH_V1` and carries validated
  per-query primitive names, calibrated or predicted latency, per-route physical
  memory, weights and search budgets. The bridge rejects inconsistent responses.

Example native build from the project root:

```bash
cmake -S core -B build/core -DCMAKE_BUILD_TYPE=Release
cmake --build build/core --target morpheus_native_search
cd backend
MORPHEUS_SEARCH_BACKEND=native python -m pytest -q tests/test_native_search_backend.py
```

A valid MWS may define up to 64 fields and 32 queries. It is **not** arbitrary
unstructured text: invalid field references, unsupported query/primitive
combinations, invalid numbers and impossible constraints must result in a
validation error or clearly report no feasible winner rather than a fabricated
answer.

## Next technical milestones (not claimed implemented)

1. Port capability filtering, cost evaluation and final candidate ranking into
   C++20 so that Python is strictly an API/request layer.
2. Move generated-artifact composition into a C++ code-generation library.
   Require compile verification, schema-based behavior tests and provenance
   before any "generated and verified" promise.
3. Offer real CSV/Parquet/database adapters with bounded profiling and clear
   operation-mix input. Data cardinality **alone** cannot reveal the desired
   future query workload, so users must supply or observe query patterns.
4. Run repeated measurements across varied real input sizes/distributions,
   train optional prediction models only on measured data, use a held-out
   evaluation set, and retain a conservative fallback when uncertain.
5. Add frontend display for native/legacy engine provenance, measured-versus-
   estimated latencies, compilation/verification status and constraint failures.

## Research rationale

Cost-driven workload-aware index selection and careful calibration are
established techniques. These references motivate the approach and are **not**
evidence that this repository has achieved their benchmark results:

- Chaudhuri and Narasayya (VLDB 1997): https://www.microsoft.com/en-us/research/publication/an-efficient-cost-driven-index-selection-tool-for-microsoft-sql-server/
- Marcus et al. (PVLDB 2020): https://vldb.org/pvldb/vol14/p1-marcus.pdf
- Schlosser et al. (2023): https://link.springer.com/article/10.1007/s42979-022-01473-7
