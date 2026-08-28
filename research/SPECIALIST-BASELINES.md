# MORPHEUS Specialist Baseline Policy

Status: IMPLEMENTED POLICY + PARTIAL ADAPTERS  
Evidence rule: benchmark availability is not benchmark superiority.

## Why this exists

`std::unordered_map` and `std::map` are useful language-standard reference baselines, but they are not enough for a serious systems paper. A fair MORPHEUS evaluation must also compare relevant primitive families against contemporary, optimized specialist implementations when their logical semantics can be matched without distortion.

This document freezes the external-baseline policy before quantitative claims are filled. Missing dependencies remain missing evidence; MORPHEUS must never replace an unavailable external system with a fabricated value or quietly compare different logical operations.

## Baseline tiers

| Tier | System | Family | MORPHEUS comparison | Integration state | Claim boundary |
|---|---|---|---|---|---|
| S0 | `std::unordered_map` | node-oriented hash table | `RobinHoodHashIndex` exact lookup/build | IMPLEMENTED | language-standard reference only |
| S0 | `std::map` | ordered tree | `BPlusTreeIndex` point/range/build | IMPLEMENTED | language-standard reference only |
| S1 | `boost::unordered_flat_map` | flat open-addressing hash | `RobinHoodHashIndex` point lookup/build | IMPLEMENTED OPTIONAL | only when public Boost header is present |
| S1 | `boost::container::flat_map` | sorted contiguous associative container | `BPlusTreeIndex` point/range/build | IMPLEMENTED OPTIONAL | different physical family, same logical ordered-map operations |
| S2 | `absl::flat_hash_map` | Swiss-table flat hash | `RobinHoodHashIndex` exact lookup/build | PLANNED EXTERNAL ADAPTER | dependency must be pinned and provenance captured |
| S2 | Folly `F14` | vector-filtered flat/value/node hash family | `RobinHoodHashIndex` exact lookup/build | PLANNED EXTERNAL ADAPTER | select the variant explicitly; do not report an ambiguous “F14” result |
| S2 | CRoaring | Roaring bitmap | MORPHEUS adaptive compressed bitmap | PLANNED EXTERNAL ADAPTER | requires matching set/bitmap semantics and linked-library provenance |
| S3 | learned/updatable index systems | learned ordered index | future learned-index MORPHEUS primitive | NOT YET SEMANTICALLY MATCHED | do not compare until MORPHEUS implements the same operation/update contract |
| S3 | storage engines / DB indexes | integrated database indexes | composite MORPHEUS artifact | STUDY-SPECIFIC ONLY | end-to-end DB semantics can dominate; requires a separate protocol |

## Primary upstream references

- Abseil container guide: https://abseil.io/docs/cpp/guides/container
- Abseil Swiss Tables design notes: https://abseil.io/about/design/swisstables
- Boost.Unordered `unordered_flat_map`: https://www.boost.org/doc/libs/latest/libs/unordered/doc/html/unordered/reference/unordered_flat_map.html
- Boost.Container `flat_map`: https://www.boost.org/doc/libs/latest/doc/html/container/non_standard_containers.html
- Folly F14 design/usage notes: https://github.com/facebook/folly/blob/main/folly/container/F14.md
- CRoaring: https://github.com/RoaringBitmap/CRoaring

These links identify implementation families; they are not evidence that one implementation is universally faster than another.

## Frozen fairness contract

For a paired primitive experiment, all of the following must hold:

1. Same logical operation and answer semantics.
2. Same key/value domain and generated logical input stream.
3. Same record count, operation count, seed and query sequence.
4. Same compiler family, language mode and optimization profile unless compiler is the independent variable.
5. Same process/run placement when practical; interleave or randomize treatment order in publication campaigns to reduce thermal/order bias.
6. Same warmup policy and repeated-sample protocol.
7. No result may be discarded because MORPHEUS loses.
8. Dependency name/version/commit, compile flags and detected feature availability must be preserved.
9. End-to-end generated composites are evaluated separately from isolated primitive microbenchmarks.
10. CI timings remain smoke/exploratory evidence and are never promoted to publication-grade performance numbers.

## Current executable adapter

`core/src/specialist_baseline_bench.cpp` compiles with zero required external library dependency. It probes public Boost headers at compile time:

- `boost/unordered/unordered_flat_map.hpp`
- `boost/container/flat_map.hpp`

If a specialist header is absent, that comparison is marked unavailable. The default smoke path still tests MORPHEUS treatments and the evidence schema. A controlled campaign can pass `--require-specialists` to fail rather than continue when these adapters are missing.

`benchmark/run_specialist_baseline_matrix.py` executes a size × seed matrix, preserves raw benchmark payloads, records machine provenance, computes paired analyses only for actually available systems, and emits a content-hashed evidence index.

## What the present adapter does not establish

It does not establish that Boost is the strongest available baseline for every workload. It does not benchmark Abseil, Folly or CRoaring yet. It does not compare allocator policies, memory RSS, concurrent operations, persistence, NUMA behavior, cold-cache behavior, or database-integrated indexes. It does not establish state-of-the-art performance.

## Next adapter order

1. Abseil `flat_hash_map` for a widely used Swiss-table hash baseline.
2. CRoaring for compressed-bitmap set operations.
3. Folly F14 only in a controlled Linux environment where dependency/toolchain reproducibility can be frozen.
4. Learned/updatable indexes only after the MORPHEUS workload contract and mutation semantics can be matched exactly.

Each new adapter must add a semantic-compatibility note, dependency provenance, deterministic smoke validation, and an explicit missing-evidence state before it becomes part of a research campaign.
