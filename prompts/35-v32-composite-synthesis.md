# MASTER PROMPT #35 — COMPOSITE SYNTHESIS, OWNERSHIP, ROUTING & UPDATE CONSISTENCY

## Mission
Turn MORPHEUS from a primitive selector into a true physical-design synthesizer. Composite configurations may combine multiple structures only when the ownership, routing, memory, update, migration and correctness semantics are explicit and empirically justified.

## Fundamental model
A composite configuration is a typed directed design graph, not a bag of data structures. Nodes represent physical stores/indexes/filters/materializations. Edges represent derivation, ownership, update dependency, query routing, projection or migration relationships.

A configuration must answer:
1. Where is authoritative logical state stored?
2. Which structures are derived or secondary?
3. Which logical operations route to which physical nodes?
4. How are writes propagated?
5. What consistency invariant must hold after every mutation?
6. How is memory counted without accidental duplication?
7. How is the design built, migrated, verified and rolled back?

## ConfigurationIR
Define a canonical/versioned ConfigurationIR with at least:
- configuration ID/hash;
- source WorkloadIR hash;
- physical nodes with implementation IDs and parameters;
- authoritative-storage marker(s);
- fields/projections owned by each node;
- logical-operation routing rules;
- mutation dependency graph;
- consistency mode;
- build order;
- migration dependencies;
- predicted raw metric vector and uncertainty;
- calibration/model provenance;
- constraints/objective identity.

Canonicalization must make semantically equivalent plans hash-equivalent where intended.

## Ownership modes
Support explicit concepts such as:
- PRIMARY: authoritative record ownership;
- SECONDARY_INDEX: derived lookup/range structure;
- FILTER: non-authoritative accelerator;
- PROJECTION: materialized subset/column view;
- CACHE: optional derived replica with freshness contract;
- GRAPH_VIEW: derived adjacency or traversal representation.

Do not let two nodes both appear authoritative unless the consistency/replication semantics are fully defined.

## Query routing
For each WorkloadIR operation produce an executable route plan:
- direct single-index route;
- index -> primary fetch;
- filter -> candidate index/store;
- bitmap intersection/union -> materialization;
- composite range/filter plan;
- fallback scan only if explicitly supported and costed.

Routing must preserve logical semantics. A cheap approximate filter may reduce candidates but cannot replace an exact answer unless the operation itself permits approximation.

## Update propagation
Mutations must maintain every dependent materialization. Define a mutation plan per insert/update/delete:
1. validate input/preconditions;
2. identify old and new indexed values where required;
3. mutate authoritative storage;
4. update/remove/add secondary entries;
5. verify or roll back on failure according to current transactional scope.

For correctness-first prototypes, rebuild-on-mutation may be valid if labeled and costed. It must not be presented as optimized incremental maintenance.

## Mutation dependency graph
Build a DAG of dependencies from authoritative state to derived indexes. Detect cycles unless a separately modeled replicated-state protocol exists. Topologically order build/rebuild/update stages.

## Consistency semantics
At minimum distinguish:
- single-threaded atomic operation semantics;
- local mutex/transaction protected semantics;
- snapshot/versioned publication semantics;
- eventual/async derived maintenance (future, if introduced).

The current implementation's guarantees must be explicit. Do not infer ACID or distributed consistency from local in-process state transitions.

## Memory accounting
Memory is computed per materialized physical node plus declared metadata. Deduplicate only genuinely shared payload/storage. Avoid deduplicating merely because two routes use the same primitive family. Record whether process RSS, allocator slack, caches and generated code are included or excluded.

## Build cost
Composite build cost includes every physical member plus routing/metadata setup. If secondary structures depend on primary IDs/slots, include mapping construction. Build may be parallelized only when dependency and memory constraints allow it.

## Update cost
Composite update cost is the weighted cost of maintaining every affected node. Exact mutation distribution identity should be consumed only when operation, implementation, scale and distribution match calibration evidence. Otherwise fall back conservatively with explicit uncertainty.

## Candidate generation
Generate compositions from workload demands rather than arbitrary Cartesian explosion. Techniques:
- group operations by field/semantic capability;
- share an index when semantics and cost justify it;
- introduce filters only when downstream selectivity benefit is plausible;
- separate point/range/filter routes when a composite may outperform one universal structure;
- constrain number of materialized nodes;
- enforce memory/build/update hard limits early.

## Search neighborhood operators
For beam/evolutionary/local search define deterministic mutations:
- replace primitive implementation;
- change primitive parameter;
- split one shared index into two route-specific indexes;
- merge compatible route indexes;
- add/remove secondary filter;
- change authoritative/secondary arrangement where legal;
- change routing to an existing compatible node.

Every mutation passes canonicalization and feasibility before scoring.

## Feasibility propagation
Reject configurations when:
- any logical operation lacks a semantically valid route;
- mutation propagation cannot maintain required consistency;
- types/fields are incompatible;
- a probabilistic component would become authoritative for an exact operation;
- hard memory/build/latency/update constraints are violated under the declared model;
- an implementation is unavailable for the target platform;
- required calibration/evidence policy forbids automatic eligibility.

## Pareto optimization
Preserve raw dimensions: latency/throughput by operation class, memory, build cost, update cost and migration cost where relevant. Apply hard constraints first. Pareto front should expose trade-offs rather than hide them behind a single score.

## Empirical finalist measurement
When feasible, benchmark finalists end-to-end because independent primitive costs may miss interaction effects. Candidate-level measurement supersedes primitive-level prediction for that exact artifact/machine/workload protocol while remaining scoped to the measured conditions.

## Correctness oracle
Generate a logical reference state independent of physical plan. Differential operation sequences compare:
- query outputs;
- duplicate behavior;
- range boundaries;
- filter exactness/approximation contract;
- post-mutation state;
- secondary-index synchronization.

Any mismatch invalidates the candidate regardless of predicted score.

## Migration
Composite migration must define source snapshot, target construction, validation, activation and rollback. Transition cost includes copy/rebuild, catch-up, validation and publication. For runtime adaptation, expected long-horizon benefit must exceed transition cost plus safety margin/hysteresis policy.

## Failure handling
If a derived update fails after primary mutation, current scope must either compensate/rollback or fail the whole operation before exposing inconsistent state. Record failure-injection tests. Never silently continue with stale secondary indexes under an exact consistency contract.

## Demonstration requirement
A strong MORPHEUS demo/research claim should include at least one heterogeneous workload where a composite configuration is compared fairly against:
- best single primitive;
- a reasonable manual composite;
- exhaustive/empirical optimum on a tractable small design space where possible.

Report when composition does not help.

## Definition of done
Composite synthesis is credible only when ConfigurationIR, ownership, routing, update propagation, memory accounting, feasibility, code generation and differential correctness all describe the same executable plan, and at least one measured experiment evaluates whether the additional complexity provides value.

## Truth boundary
"Composite synthesis" means MORPHEUS can construct and verify multiple cooperating physical structures. It does not imply a general-purpose database optimizer, distributed transaction engine or globally optimal design over an unbounded structure universe.