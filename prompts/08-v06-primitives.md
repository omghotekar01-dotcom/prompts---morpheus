# MASTER PROMPT #8 — VOLUME 6: PRIMITIVE LIBRARY, CAPABILITY ALGEBRA & COMPOSITION CONTRACTS

## Mission
Build the substrate from which MORPHEUS synthesizes physical representations. A primitive is not merely an implementation of a textbook DSA; it is a measurable, parameterized, machine-aware building block with formal capabilities, semantic preconditions, lifecycle/update behavior, memory/build/operation cost evidence and safe composition interfaces.

MORPHEUS's source architecture explicitly calls for a primitive library spanning structures such as hash tables, B+ trees, sorted arrays, tries, bitmaps and CSR, with measured performance statistics feeding a cost model and composition search. Implement that idea rigorously rather than collecting disconnected demos.

## 1. Core abstraction
Define:
```text
PrimitiveDescriptor = identity + version + semantic capabilities + type/domain requirements + parameter schema + lifecycle properties + model feature contract + implementation artifact.
PrimitiveInstance = descriptor + concrete parameters + target fields + machine context.
```
Descriptor is immutable registry metadata. Instance is a candidate component.

## 2. Capability algebra
Represent operations as capabilities, not marketing labels:
`ExactLookup`, `EqualityFilter`, `RangeLookup`, `OrderedIteration`, `PrefixLookup`, `Membership`, `Insert`, `Delete`, `Modify`, optionally `Rank/Select`, graph-neighbor traversal later.

Each capability records exact semantics: supported key types; unique/non-unique; ordering requirement; exact/approximate result; false-positive/negative policy; output ordering; mutation support; concurrency/durability status; expected complexity as descriptive metadata only—not the empirical cost model.

A Bloom filter can support approximate membership but cannot independently satisfy an exact membership query requiring zero false positives. Capability matching must encode this distinction.

## 3. Primitive contract
Every primitive MUST expose conceptual operations:
```text
validate(instance, workload_fragment)
build(records)
query(operation)
insert(record)
delete(record/key)
modify(old,new)
memory_usage()
statistics()
serialize? / restore? (future)
```
Generated implementations and benchmark adapters must share semantics.

## 4. Initial library
Build a scientifically manageable first set:
1. Robin Hood/open-addressing hash index — exact lookup/equality.
2. Sorted contiguous array — binary lookup/range/ordered scan; expensive mutation.
3. B+ tree — exact/range/mutable ordered index.
4. Trie/radix trie — string prefix/exact.
5. Bitmap/Roaring-style index — low/moderate-cardinality equality/filter composition.
Optional after proof: skip list, Bloom filter, CSR, LSM-like structure, learned index.

Do not begin with 20 primitives. The formal theory requires exhaustive-oracle comparisons on small spaces and measured finalist validation.

## 5. Record ownership
Separate primary record storage from secondary indexes. Define stable `RecordId`/row handle contract. Secondary indexes map key → RecordId(s), unless a primitive explicitly owns records. This makes composite structures possible without uncontrolled duplication.

## 6. Primary storage choices
Model physical record store explicitly (AoS/SoA/packed/arena only when implemented). Candidate memory must include record storage + indexes + allocator overhead + metadata. Never compare one candidate including base records against another excluding them.

## 7. Hash primitive parameters
Examples: initial capacity policy, max load factor, hash family, probe strategy, key storage policy. Track expected probe counts and measured latency by load factor/key type/hit rate/access skew. Rehash/build/mutation cost must be measured.

## 8. Sorted-array parameters
Key layout, RecordId layout, duplicate handling, rebuild policy. Exact/range lookup can exploit cache locality; inserts/deletes may be costly. Cost model must distinguish static/read-mostly cases from mutable workloads.

## 9. B+ tree parameters
Node/page size, fanout derived from key/pointer sizes, leaf payload, duplicate strategy. For an in-memory MVP, do not pretend disk-page semantics unless actually measured. Expose tree height, occupancy and node bytes as observable stats.

## 10. Trie parameters
Alphabet/encoding policy, node representation, path compression/radix mode, child container strategy. Unicode semantics must be explicit; Alpha can restrict to byte strings if documented. Memory can dominate, so real measurements are mandatory.

## 11. Bitmap parameters
Field cardinality/domain mapping, bitmap representation, compression strategy if supported. Capability precondition depends strongly on cardinality and result semantics. Composite intersections/unions should later become first-class query-plan operations.

## 12. Approximate structures
Approximate primitives must declare error semantics. Example Bloom descriptor includes false-positive rate, no false negatives under supported operations, memory formula and update constraints. Search cannot route an exact-return operation solely to approximate structure; it may use filter→exact-verification composition.

## 13. Descriptor schema
```text
PrimitiveDescriptor {
 PrimitiveId id; SemVer version; string name;
 set<Capability> capabilities;
 TypePredicate key_types;
 Preconditions preconditions;
 ParameterSchema parameters;
 MutationProfile mutations;
 ConcurrencyLevel concurrency;
 Exactness exactness;
 ModelFeatureSchema model_features;
 ImplementationRef implementation;
}
```

## 14. Parameter schema
Strong typed parameter definitions with range/enums/defaults and conditional constraints. Candidate generation operates from schema; no magic optimizer-specific constants. Every chosen parameter appears in ConfigurationIR and explanation.

## 15. Preconditions
Examples: prefix primitive requires string/bytes key; bitmap may require bounded/cardinality-known domain; learned index requires numeric/orderable distribution assumptions; CSR requires graph-like immutable adjacency data. Preconditions are executable predicates over WorkloadIR/field stats.

## 16. Capability matching
Implement `satisfies(PrimitiveInstance, OperationRequirement) -> MatchResult`. Return supported/unsupported plus reason and optional caveats. Search uses this rather than giant if/else chains.

## 17. Coverage
For candidate C and workload operation o, define coverage `cover(C,o)` if at least one legal route can satisfy o. A candidate is semantically feasible only if every required operation has a correctness-preserving route. Performance constraints are evaluated afterward.

## 18. Composition model
A configuration is a graph, not just a set:
```text
RecordStore
├─ Hash(product_id)
├─ BPlus(price)
├─ Bitmap(category)
└─ Trie(name)
```
Edges encode record-ID linkage, maintenance dependencies and query routes. Multiple structures may cover one operation; one structure may cover many.

## 19. Query routing
Create `AccessRoute`:
`operation_id, primitive_instance_ids, route_kind, estimated_cost, exactness, result_ordering`.
Route kinds: direct, filter_then_verify, intersection, union, scan_fallback (only if permitted). Search evaluates configuration + routes together.

## 20. Maintenance graph
Every write identifies affected indexes. Insert/update/delete cost is aggregate/critical-path according to execution semantics. Correctness requires atomic logical maintenance; MVP can perform sequential single-thread updates but tests must ensure all indexes remain synchronized.

## 21. Configuration feasibility
Check: operation coverage; primitive preconditions; type compatibility; hard resource constraints; mutation compatibility; concurrency/durability capability; parameter validity; composition conflicts; generated-code support. Return structured rejection reason.

## 22. Memory accounting
Every primitive implements measured/estimated memory decomposition:
`payload, keys, record_ids, buckets/nodes/bitmaps, allocator overhead, alignment, metadata, slack/reserve`. Compare model prediction to actual process/container allocation where feasible. Report both logical and resident/allocated bytes when relevant.

## 23. Build cost
Measure construction time and temporary peak memory. Runtime adaptation depends on migration/build cost, so build cannot be treated as free.

## 24. Update cost
Measure insert/delete/modify separately. Modify of an indexed field may require remove+insert. Modify of unindexed payload should not pay unrelated index cost. WorkloadIR's field modification probabilities feed this model.

## 25. Machine awareness
Primitive performance is indexed by machine profile: CPU model/features, cache sizes, memory, compiler/version/flags, OS and relevant allocator. Big-O is explanatory; machine-calibrated evidence selects candidates.

## 26. Microbenchmark matrix
For each primitive vary meaningful dimensions: N, key type/size, cardinality, hit rate, selectivity, access skew, load factor/fanout/prefix length, read/write ratio. Avoid full Cartesian explosion; use designed experiments/adaptive calibration later.

## 27. Benchmark protocol
Warmup; multiple repetitions; fixed seeds; isolate build from query; prevent dead-code elimination; verify outputs; record compiler/flags; pin CPU/affinity when possible; record distribution and cache mode; store raw samples, not only averages. Report median/p95/p99 where statistically justified.

## 28. Correctness oracle
Every primitive test compares against simple reference semantics (`unordered_map`, sorted vector/reference scan, etc.) across randomized operation sequences. Performance is irrelevant if semantics diverge.

## 29. Differential testing
Run same generated operation trace against candidate composite configuration and canonical reference store. Compare exact returned RecordId sets/order according to operation contract after every mutation batch.

## 30. Property tests
Examples: inserting then exact lookup returns record; deleting removes it; range results satisfy bounds; prefix results share prefix; index rebuild preserves logical results; duplicate-key semantics hold; bitmap intersection equals reference set intersection.

## 31. Primitive registry
Central versioned registry loads descriptors and implementation factories. Search enumerates registry, never hardcodes primitive list. Registry hash is part of experiment provenance/configuration lock.

## 32. Plugin boundary future
Third-party primitive plugin must provide descriptor, implementation, benchmark adapter, correctness adapter, cost-model feature contract and version. Treat plugin code as trusted native extension initially; sandboxing is separate research/product work.

## 33. Cost evidence interface
Primitive does not decide its own optimizer score. It emits features/evidence; CostModel predicts metrics. Define `PrimitiveFeatureVector` from N/type/cardinality/selectivity/parameters/machine. Keep measurement database separate from descriptor.

## 34. Evidence store
Store rows keyed by primitive version + parameterization + workload point + machine profile + compiler + benchmark protocol + seed/repetition. Raw samples can live compressed outside Git prompt repo; metadata/results in experiment DB.

## 35. Complexity metadata
Descriptors may expose theoretical complexity (`expected O(1)`, `O(log N)`, etc.) for explanations/sanity checks. Never substitute complexity class for empirical latency.

## 36. Candidate deduplication
Canonicalize primitive instances and configuration graphs. Semantically identical configurations must hash identically independent of insertion order. Prevent search budget waste.

## 37. Dominance pruning
A primitive instance may be pruned when another instance has identical capability/semantics and is demonstrably no worse across relevant predicted metrics under current workload, with uncertainty-aware caution.

## 38. Baselines
Include standard-library/manual baselines as benchmark competitors, but label whether they are part of synthesis search or external evaluation. Useful: unordered_map, map, sorted vector + binary search, linear scan and a hand-composed reference.

## 39. Code-generation contract
Each primitive implementation exposes template/component metadata so ConfigurationIR can instantiate it. Generated API must not know concrete structures. Use generated `MorpheusStore` facade with operation-specific methods routed to selected components.

## 40. Runtime migration contract
Primitive must declare build-from-records and incremental migration capability. `MigrationEstimator` needs bytes to allocate, build time, temporary peak memory, synchronization needs and rollback support. Alpha can use stop-the-world/offline rebuild; label it accurately.

## 41. Safety
No arbitrary template injection; registry implementations are code-reviewed/versioned; parameters validated; memory arithmetic overflow-checked; generated allocations checked; benchmark inputs bounded; malformed data cannot corrupt registry state.

## 42. Suggested C++ structure
```text
core/include/morpheus/primitives/{Descriptor,Capability,Registry,Instance}.hpp
core/primitives/hash/
core/primitives/sorted_array/
core/primitives/bplus/
core/primitives/trie/
core/primitives/bitmap/
core/benchmark/
```
Each primitive folder: implementation, descriptor factory, benchmark adapter, tests.

## 43. Search-facing API
```text
registry.compatible_instances(field, operation_requirements, parameter_budget)
configuration.coverage()
configuration.maintenance_dependencies()
configuration.memory_features()
configuration.codegen_support()
```
Keep search algorithm independent of concrete classes.

## 44. MVP candidate space
For first proof: one primary record store + optional hash on ID + optional B+ tree/sorted array on numeric range field. Exhaustively enumerate this tiny space and establish empirical optimum. Then add trie/bitmap and beam search.

## 45. Research experiments
Ablate primitives: how much does each expand achievable Pareto frontier? Compare single-structure vs composite synthesis. Measure predicted vs observed primitive costs, configuration cost error and optimizer top-k recall. Test cross-machine ranking changes. These results are stronger than merely showing a flashy dashboard.

## 46. Novelty discipline
Do not claim individual hash/tree/trie implementations are novel. Potential research value lies in formal capability-driven composition, hardware/workload-aware synthesis, empirical cost calibration, code generation and transition-aware adaptation. Prior-art verification remains mandatory before patent claims.

## 47. Acceptance gates
Every registered primitive has: unique versioned ID; typed parameters; executable preconditions; formal capabilities/exactness; correctness tests; mutation tests; benchmark adapter; memory/build/update accounting; cost-model feature contract; codegen support or explicit unsupported status; machine-profile provenance. Composite configs maintain consistency and every operation route is correctness-valid.

## 48. Build order
Capability/type algebra → record-store/RecordId contract → descriptor/registry → hash → sorted array → B+ tree → correctness harness → benchmark harness → memory/build/update metrics → composition graph/routes → trie → bitmap → migration hooks → advanced primitives.

## North star
MORPHEUS does not choose names such as “B+ tree” because a textbook says they are good. It reasons over verified capabilities and measured tradeoffs of concrete primitive instances under a specific WorkloadIR and machine. The primitive library is therefore MORPHEUS's physical vocabulary; composition is its grammar.

**NEXT: MASTER PROMPT #9 — VOLUME 7: EMPIRICAL COST MODEL, HARDWARE CALIBRATION, UNCERTAINTY & ACTIVE MEASUREMENT.**
