# MASTER PROMPT #34 — ADVANCED DATA-STRUCTURE & PRIMITIVE ENCYCLOPEDIA

## Mission
Expand MORPHEUS's primitive vocabulary systematically while preserving a strict distinction between implemented/tested primitives and future/research candidates. The optimizer must reason from capability manifests and measured evidence, not from marketing names.

## Primitive manifest template
Every primitive family or implementation variant must define:
- canonical primitive ID;
- implementation ID/version;
- logical capabilities;
- supported key/value types;
- duplicate semantics;
- ordering semantics;
- mutation semantics;
- concurrency semantics;
- persistence/durability semantics if any;
- parameter schema and bounded domain;
- memory ownership/lifecycle;
- asymptotic expectations;
- likely hardware behavior;
- build/update/migration characteristics;
- composition role;
- correctness oracle strategy;
- benchmark plan;
- maturity state: IMPLEMENTED, GUARDED, RESEARCH or PLANNED.

No primitive enters automatic search solely because its name appears in this encyclopedia.

## Hash-index families
Cover and compare:
- Robin Hood/open addressing;
- linear/quadratic probing;
- Swiss-table/control-byte style families;
- cuckoo hashing;
- hopscotch concepts;
- chained hash tables;
- extendible/linear hashing for persistence.

Relevant parameters: load factor, growth policy, probe metadata, hash function, bucket width, tombstone policy. Measure hit/miss/update behavior under uniform and skewed distributions.

## Ordered indexes
Cover:
- balanced BST reference (`std::map`/red-black class);
- B-tree/B+ tree;
- B* / Bε-tree concepts;
- skip lists;
- sorted vectors/arrays;
- learned ordered indexes as separate research families.

Key dimensions: fanout, node size, cache locality, range throughput, mutation amplification, erase/merge behavior and bulk-load support.

## Trie/radix families
Cover:
- byte/character trie;
- Patricia/radix trie;
- adaptive radix tree (ART);
- compressed prefix/suffix variants;
- crit-bit concepts.

Track alphabet/key encoding, node representation, prefix semantics, memory overhead and update cost. Strings/byte keys are not interchangeable with arbitrary numeric ordering without an explicit encoding.

## Bitmap/posting structures
Cover:
- dense bitsets;
- posting vectors;
- run-length encoded bitmaps;
- Roaring-style containerized bitmaps;
- EWAH/WAH concepts;
- sparse/dense adaptive containers.

Operations: contains, filter/materialize, intersection, union, difference, rank/select if supported. Parameters: container threshold, block size, compression mode. Memory accounting must include metadata.

## Probabilistic membership filters
Cover:
- Bloom filter;
- blocked Bloom;
- Cuckoo filter;
- XOR/fuse-filter concepts.

These are typically secondary accelerators, not authoritative stores. Manifest must declare false-positive behavior and whether false negatives are impossible under supported operations. Cost objective may include memory and expected downstream lookup reduction.

## LSM and write-optimized concepts
Cover as advanced/future families:
- LSM-tree;
- leveled/tiered compaction;
- memtable + immutable runs;
- Bε-tree/fractal-tree ideas.

Model write amplification, read amplification, compaction debt, space amplification, tail-latency effects and durability assumptions. Do not treat a toy in-memory sorted-vector merge as a production LSM implementation.

## Range/aggregate structures
Cover:
- Fenwick tree;
- segment tree;
- sparse table for immutable data;
- interval tree;
- order-statistics trees.

These apply only when workload semantics expose corresponding aggregate/range operations.

## Priority structures
Cover:
- binary/d-ary heap;
- pairing heap;
- radix heap for constrained integer monotonic workloads;
- bucket queues.

Expose priority/decrease-key/delete requirements explicitly; do not route arbitrary ordered queries to a heap.

## Spatial/multidimensional structures
Research/advanced candidates:
- k-d tree;
- quadtree/octree;
- R-tree/R*-tree;
- grid/hash spatial indexes;
- Z-order/Morton layout.

Require multidimensional query semantics in MWS/IR before these become eligible. Include dimension count, metric, bounding boxes/radius and update patterns.

## Graph representations
Cover:
- CSR/CSC immutable/semi-static adjacency;
- adjacency vectors;
- hash-based dynamic adjacency;
- edge lists;
- compressed/succinct graph concepts.

Capabilities distinguish neighbor lookup, edge existence, BFS/scan, weighted edge access, updates and batch rebuilds. Graph algorithms are not automatically implied by storage representation.

## Succinct/compressed structures
Research families:
- succinct bitvectors with rank/select;
- wavelet trees/matrices;
- Elias-Fano ordered sets;
- front-coded dictionaries;
- compressed tries;
- learned/succinct hybrids.

Compression changes CPU/memory trade-offs; benchmark decompression and random access separately.

## Learned indexes
Treat learned indexes as model-assisted physical structures, not AI magic. Candidate families may include:
- RMI-style models;
- PGM-style piecewise models;
- ALEX-style adaptive learned indexes;
- learned Bloom/filter variants.

Required manifest fields include model architecture/class, training/build cost, model size, fallback/search bound, retraining/update semantics and distribution-shift sensitivity. Keep intellectual-property/license considerations visible.

## Persistent/storage-engine structures
Future scope may include page-oriented B+ trees, copy-on-write trees, log-structured layouts, mmap indexes and persistent-memory layouts. These require crash/recovery semantics, I/O models and durability tests that are distinct from the current in-memory prototype.

## Concurrency variants
Concurrency is an implementation dimension, not a primitive label. Candidate variants may be single-threaded, mutex/RW-lock, sharded, lock-free or RCU/epoch-based. Automatic eligibility requires stress testing and a clear memory reclamation model.

## Capability algebra
Represent operation support declaratively. Capabilities should include semantic qualifiers such as:
- exact vs probabilistic;
- ordered vs unordered;
- duplicate/multivalue;
- mutable vs immutable/batch;
- prefix/range/filter/neighbor;
- concurrency level;
- persistence level.

A composition is feasible only if every required logical operation has a semantically valid route.

## Parameter search
Primitive parameters participate in ConfigurationIR and search. Use bounded/discretized spaces initially. Examples: hash load factor, B+ fanout/node target, bitmap threshold, Bloom bits-per-key/hash count, LSM fanout/level policy. Track parameter provenance and avoid huge unconstrained combinatorics.

## Correctness protocol
Each implemented primitive needs:
- deterministic unit corpus;
- property/state-machine tests;
- duplicate/empty/boundary cases;
- differential comparison against a simple reference;
- serialization/migration tests if supported;
- sanitizer/fuzz coverage for native code.

## Benchmark protocol
Benchmark per operation and distribution, including hit/miss where applicable. Record build, memory and mutation separately. Prefer parameter sweeps that reveal crossover points rather than one arbitrary setting.

## Admission policy
A new primitive moves through:
PLANNED -> IMPLEMENTED_REFERENCE -> CORRECTNESS_VERIFIED -> BENCHMARK_CALIBRATED -> SEARCH_ELIGIBLE -> optional RUNTIME_ELIGIBLE.

Promotion requires evidence and registry/version changes. Research-only implementations cannot silently become automatic controls.

## Current-vs-future truth boundary
The existence of this catalog does not mean all listed structures are implemented. The runtime capability registry and tested code are authoritative. Documentation must label every family accordingly.

## Definition of done
This volume is complete as an engineering specification when MORPHEUS has a uniform manifest model, admission workflow, correctness/benchmark template and extensible catalog capable of adding these families without rewriting the optimizer.