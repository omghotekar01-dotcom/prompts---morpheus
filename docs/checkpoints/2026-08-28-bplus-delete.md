# MORPHEUS P2 Checkpoint — Rebalancing B+ Tree Deletion

Date: 2026-08-28

## Problem closed by this checkpoint

The legacy `OrderedTreeIndex` implements real B+ tree lookup, range scanning and insertion, but its erase path is correctness-first: a single deletion materializes all rows, resets the tree and reinserts every remaining row. This is deliberately retained as a baseline until migration is complete.

## New implementation

`core/include/morpheus/bplus_tree.hpp` adds `BPlusTreeIndex`, a dependency-free C++20 B+ tree with incremental deletion:

- local leaf borrowing from left/right siblings;
- local leaf merging with linked-leaf repair;
- internal-child borrowing and merging;
- separator regeneration from right-child first keys;
- recursive parent underflow repair;
- root collapse after merges;
- point lookup, range scan, insert/update, erase, ordered materialization, height and structural validation.

The implementation maintains explicit non-root occupancy checks in `validate()` and keeps internal separator keys derived from child subtrees rather than treating them as independent payload keys.

## Correctness evidence

`core/tests/test_bplus_tree.cpp` performs deterministic differential/stress testing against `std::map` with fanouts 3, 4 and 5. It inserts hundreds of shuffled keys, performs updates, deletes every key in shuffled order, validates repeatedly during deletion, verifies missing-key erase behavior, exercises ranges and forces root collapse to a single empty leaf.

The new test target is registered with CMake/CTest. GitHub Actions run `33148554874` reached a successful Ubuntu C++20 build/test job containing this test; at the observation boundary the overall cross-platform run was still executing, so this document does not claim the entire run green.

## Performance evidence pipeline

The ordered-index erase benchmark now compares three implementations on identical insertion/delete sequences:

1. `ordered_tree_rebuild` — legacy full-rebuild erase baseline;
2. `bplus_tree_rebalanced` — new incremental deletion implementation;
3. `std_map` — standard-library reference baseline.

The benchmark verifies final cardinality and checksum equivalence across all three implementations before timing evidence is accepted.

`scripts/sweep_ordered_tree_erase.py` runs deterministic size/seed sweeps and rejects schema drift, metadata mismatch, invalid timings, result-size mismatch or checksum disagreement.

`scripts/analyze_ordered_tree_erase.py` reports per-size medians plus:

- rebalanced/legacy timing ratio;
- rebalanced speedup versus legacy;
- rebalanced/std::map timing ratio;
- rebalanced slowdown versus `std::map` when present.

The CI smoke gate executes the three-way comparison at sizes 256 and 512 across seeds 1337 and 7331. CI timing remains smoke evidence only; it is not publication-grade performance evidence.

## Related bitmap evidence closure

GitHub Actions run `33148209223` completed successfully for commit `9ac0f27f418d511a4c911bcd4d2c88403d6a121f`, validating the sparse/dense crossover sweep, analysis and conservative threshold-recommendation gate. This closes the CI evidence gap for that instrumentation while production bitmap thresholds remain unchanged pending controlled hardware measurements.

## Truth boundaries

- `BPlusTreeIndex` is now a tested standalone primitive; the legacy `OrderedTreeIndex` has not yet been replaced in every consumer.
- CI benchmark timing is useful for execution/data-contract validation, not for scientific speedup claims.
- The next migration step must preserve generated-artifact semantics and rerun differential, sanitizer and cross-platform gates before the rebuild-based path is retired.
- No performance claim should be made from a single CI machine or smoke repetition.

## Next

1. Close the full cross-platform CI run for the rebalancing primitive and three-way benchmark pipeline.
2. Identify all ordered-index consumers/code-generation paths and migrate them to `BPlusTreeIndex` behind tests.
3. Run a larger declared-hardware erase sweep and preserve raw evidence.
4. Remove or explicitly deprecate the rebuild-based erase implementation only after migration evidence is green.
5. Continue the remaining P2/P3 closure program, then advance Butterfly Engine according to project priority.
