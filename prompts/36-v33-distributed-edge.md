# MASTER PROMPT #36 — DISTRIBUTED, EDGE & EMBEDDED MORPHEUS

## Mission
Define how MORPHEUS could extend beyond a single local process while preventing future-scope concepts from contaminating current implementation claims. Distributed and embedded design require new cost terms, failure models, consistency semantics and platform constraints; they are not automatic consequences of the local engine.

## Scope discipline
Separate three execution classes:
1. LOCAL_SINGLE_NODE — current/default research prototype scope unless code states otherwise.
2. DISTRIBUTED_MULTI_NODE — future/advanced scope requiring network/failure/replication semantics.
3. EDGE_EMBEDDED — future/advanced scope requiring memory, flash, power and real-time constraints.

Every artifact/configuration declares its execution class.

# Part I — Distributed MORPHEUS

## Distributed physical design
A distributed ConfigurationIR must add:
- node/region topology;
- partitioning/sharding policy;
- replication factor and placement;
- consistency model;
- ownership/leader policy;
- network routing plan;
- failure/recovery policy;
- migration/rebalancing plan;
- per-node and aggregate resource constraints.

## Partitioning
Candidate strategies may include:
- hash partitioning;
- range partitioning;
- consistent hashing;
- workload-aware/hot-key partitioning;
- graph partitioning;
- replicated small dimensions/lookups.

Partition key selection becomes part of optimization. Model skew and hotspot movement explicitly.

## Replication
Replication is not free. Model:
- write amplification;
- quorum/ack latency;
- read locality;
- failover benefit;
- storage overhead;
- consistency staleness where applicable.

Do not use "replicated" without defining consistency and failure semantics.

## Consistency models
Future distributed implementations must declare one of clearly defined models, such as linearizable, sequentially consistent, snapshot, read-your-writes, bounded staleness or eventual consistency. The optimizer cannot trade consistency for latency unless the workload specification explicitly permits it.

## Network cost
Add measurable features:
- RTT/latency distribution;
- bandwidth;
- serialization bytes;
- fan-out count;
- cross-zone/region cost;
- retry probability;
- queueing/load.

Network costs must be calibrated or conservatively modeled. CI on localhost is not evidence for distributed performance.

## Failure model
Distributed experiments should include controlled failures:
- node crash/restart;
- network delay/loss;
- partition;
- leader/owner failure;
- stale replica;
- partial migration/rebalance.

Correctness criteria depend on declared consistency. Record recovery time/data loss where relevant.

## Distributed search
Search-space dimensions include primitive choice per shard, partitioning, replica placement, routing, cache/materialization placement and migration strategy. Use hierarchical search and strong feasibility pruning; avoid naive Cartesian explosion.

## Rebalancing/adaptation
Runtime adaptation may include shard split/merge, replica movement or repartitioning. Transition cost must include data transfer, catch-up, temporary duplication, network saturation and consistency validation. Require cooldown/hysteresis and rollback/failover plans.

## Distributed observability
ObservedWorkloadSnapshot may include per-node QPS, skew, queue depth, p95/p99 network latency, replica lag, hotspot keys/partitions and failure state. Never rewrite declared workload with telemetry; create immutable observed snapshots.

# Part II — Edge and Embedded MORPHEUS

## Edge constraints
Add hard constraints such as:
- RAM limit;
- flash/ROM limit;
- maximum code size;
- maximum heap allocation;
- CPU budget;
- energy/power budget if measured;
- real-time deadline;
- storage wear/endurance;
- offline/network intermittency.

## Embedded execution profiles
Potential targets include Linux ARM SBCs, RTOS/MCU-class systems and offline industrial/IoT devices. Each requires a separate validated toolchain/profile. Do not claim MCU support because ARM64 Linux builds.

## Allocation policy
Embedded candidates may require static allocation, arenas or bounded pools. If no-heap or bounded-heap operation is required, encode it as a hard capability/constraint and test allocation behavior.

## Flash/storage wear
For persistent edge designs, mutation cost may include erase/program amplification and endurance. LSM/log structures may help sequential writes but increase compaction and space amplification. These need device-specific evidence.

## Real-time behavior
Average latency is insufficient for deadline systems. Define worst-case or high-percentile requirements and scheduling assumptions. A general Linux p99 proxy is not a hard real-time proof.

## Power/energy
Energy optimization requires real measurement (on-device counters/external meter) or a clearly labeled proxy. Never convert CPU time to exact energy without validation.

## Offline synthesis
For constrained devices, MORPHEUS can synthesize on a workstation and deploy a compact artifact/profile. Runtime adaptation on-device may be limited to switching among pre-verified variants rather than compiling locally.

## Cross-compilation
Generated artifacts must record target triple, compiler, ABI/ISA requirements and configuration hash. Test through target execution or emulator where appropriate; compilation alone does not verify runtime compatibility.

## Edge safety
Industrial/medical/safety-critical environments require domain certification processes outside MORPHEUS's generic engineering gates. Do not claim SIL/ASIL/FDA/medical certification or safety guarantees without the corresponding process.

# Research plan
Potential research questions:
- Can topology-aware composition outperform per-node independent selection?
- How much calibration is required to transfer designs across heterogeneous nodes?
- When does repartitioning pay back transition cost under skew drift?
- Can offline synthesis improve memory/latency on constrained devices over standard containers?
- Can uncertainty-aware variant selection reduce deadline violations under changing edge workloads?

## Experiment requirements
Distributed claims require multi-node or controlled network emulation plus frozen topology/workload/failure protocol. Edge claims require real target hardware or a clearly labeled simulator/emulator, with target-specific measurements for claimed effects.

## Current truth boundary
Unless the repository contains implemented/tested modules stating otherwise, MORPHEUS remains a local single-node system. This volume defines a future-compatible architecture and research frontier; it must never be used to market distributed or embedded support prematurely.

## Definition of done for future promotion
A distributed/edge capability moves from RESEARCH/PLANNED to GUARDED/STABLE only after:
- typed contracts exist;
- target-specific implementation exists;
- correctness/failure tests pass;
- performance/resource protocol is measured;
- migration/rollback semantics are demonstrated where applicable;
- CI or reproducible target validation is available;
- feature registry explicitly promotes it.