# MORPHEUS Evolution Status — E32

## Checkpoint

**E32 — Read-Only SQLite Identity-Domain and Transaction-Cleanup Evidence**

This checkpoint records only evidence verified on exact implementation/test head `2c3f87a8af30f5cf29bf0828129483495f20eb30` by MORPHEUS CI run **1155** (`34179003597`), which completed successfully before this status document was created.

The evidence-bearing changes are:

- `a0c35fde7a05c7c90915ec1c183dd88fb509f412` — adds focused regression coverage for invalid caller identity rejection, persisted-domain failure cleanup, subsequent valid write/read recovery, and repeated failed observations without retained SQLite write-blocking locks.
- `2c3f87a8af30f5cf29bf0828129483495f20eb30` — corrects the repeated-failure fixture to use schema-valid but snapshot-domain-invalid whitespace mutation identity rather than a value rejected by the repository-created SQLite CHECK constraint.

## Verified capability

For the exercised local SQLite observation path, MORPHEUS now demonstrates that snapshot failures caused by invalid caller identities or persisted-domain rejection do not leave the exercised read transaction/connection holding a write-blocking SQLite lock after the call returns.

The verified path covers:

- empty and whitespace-only caller `resource_id` rejection;
- empty and whitespace-only caller `fencing_authority_id` rejection;
- a schema-valid but domain-invalid persisted mutation identity causing fail-closed observation rejection;
- immediate acquisition of an independent `BEGIN IMMEDIATE` write transaction after failed observation;
- restoration of the deliberately malformed test row followed by a repository protected-resource mutation and a valid transaction-consistent read;
- repeated failed observations followed by independent write-lock acquisition without accumulated lock leakage in the exercised process;
- automatic control, activation, and production traffic switching remaining denied.

## Scientific and production truth boundary

E32 is **local SQLite caller-identity validation and returned-call transaction-cleanup evidence only**.

The evidence shows cleanup behavior after the exercised Python calls return normally by raising `ValueError`; it does not establish crash cleanup, process-kill recovery beyond separately recorded gates, arbitrary exception safety outside the exercised path, lock-free or wait-free progress, starvation freedom, bounded production latency, filesystem guarantees, storage-device correctness, distributed lock behavior, cross-host linearizability, consensus, leases, network-partition safety, power-loss durability, safe cutover, production failover, HA/SLA behavior, production activation, production traffic switching, or production readiness.

The short SQLite busy timeouts in these deterministic tests are test controls for detecting leaked local locks. They are not latency benchmarks, service-level objectives, or performance measurements.

No throughput, scaling, benchmark-superiority, performance-superiority, novelty, patentability, state-of-the-art, or scientific-effect claim is made.

`automatic_control_allowed`, `activation_allowed`, and `traffic_switching_allowed` remain false.

## Next evidence dependency

The next dependency-ready gate is **bounded read-only SQLite lock-contention and post-timeout recovery evidence**.

Hold a local SQLite lock state that prevents the observation transaction from completing, use the reader's configured busy timeout to require a bounded fail-closed outcome, then release the blocker and prove that the same reader can subsequently obtain a valid transaction-consistent pair. The test should also verify that a contention failure does not alter fencing/resource state and does not grant any control, activation, or traffic-switching authority.

This gate must remain a deterministic local SQLite contention/recovery reference test. Timing assertions should use only a generous upper guard needed to detect unbounded hanging; they must not be reported as latency, throughput, SLA, lock-freedom, fairness, production-availability, distributed-consistency, or performance evidence.
