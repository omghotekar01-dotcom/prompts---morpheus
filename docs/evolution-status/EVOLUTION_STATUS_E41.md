# MORPHEUS Evolution Status — E41

## Checkpoint

**E41 — Cross-Process Local SQLite Parent-Forced Uncommitted Schema-Replacement Termination Containment Evidence**

This checkpoint records only evidence verified on exact head `526513393402f1098c9c33f8c65b0f474e355e8e` by MORPHEUS CI run **1176** (`34207474953`), which completed successfully before this status document was created.

The evidence-bearing changes are:

- `925aa066a8d13583ed934e2b797ffb66e655fbfa` — adds spawned-process evidence in which a child stages an incompatible protected-resource schema replacement inside an uncommitted SQLite transaction and remains alive while the parent externally invokes the multiprocessing termination path.
- `526513393402f1098c9c33f8c65b0f474e355e8e` — stabilizes an existing schema/read-race fixture on Windows CI by widening only its test hang guard; it does not change the parent-forced termination semantics or create a performance claim.

## Verified capability

For the exercised local-host Python multiprocessing/SQLite path, MORPHEUS now demonstrates containment of an uncommitted incompatible schema replacement when the parent externally terminates the child process.

The verified path covers:

- beginning from a valid committed fencing/resource pair;
- constructing and successfully using a read-only transaction-consistent reader before the child transaction begins;
- an independently spawned child beginning `BEGIN IMMEDIATE`, renaming the protected-resource table, and creating an incompatible replacement that omits `last_mutation_id` while leaving the transaction uncommitted;
- parent observation while that incompatible DDL is still uncommitted, with the parent continuing to observe exactly the last committed coherent fencing/resource pair;
- termination initiated by the parent through Python multiprocessing process control rather than child application code choosing commit, rollback, close, or `os._exit()`;
- survival of only the original committed protected-resource schema and disappearance of the uncommitted renamed staging table after the child exits;
- preservation of the committed fencing counter, resource version, mutation identity, and value;
- release of the exercised SQLite write lock, demonstrated by a later independent `BEGIN IMMEDIATE` acquisition;
- continued coherent observation by the already-constructed reader and successful independent validation by a fresh reader;
- a later valid fenced-resource successor mutation and coherent readback remaining possible;
- automatic control, activation, and production traffic switching remaining denied.

CI run 1175 on the initial evidence commit failed only in the Windows Python 3.14 + MSVC lane. The later exact head `526513393402f1098c9c33f8c65b0f474e355e8e` completed the full MORPHEUS CI matrix successfully after a scheduler-tolerant test-only stabilization in a pre-existing schema/read race. E41 therefore relies on the verified exact head, not the failed intermediate run.

## Scientific and production truth boundary

E41 is **local-host Python multiprocessing/SQLite parent-forced process-termination containment evidence only**.

It does not establish power-loss durability, kernel-crash recovery, machine-reboot recovery, filesystem/storage fault tolerance, arbitrary crash recovery, arbitrary schema-migration rollback correctness, every operating-system kill mechanism, tamper resistance, cryptographic integrity, a security boundary, distributed schema agreement, cross-host consistency, linearizability, consensus, network-partition safety, HA/SLA behavior, zero-downtime deployment, production activation, production traffic switching, or production readiness.

`multiprocessing.Process.terminate()` has platform/runtime-specific semantics. This evidence applies only to the exercised CI environments and code path and must not be generalized to stronger or different process-death mechanisms.

All synchronization waits and timeouts in these fixtures are deadlock/hang guards for the tests. They are not latency, throughput, responsiveness, scalability, or benchmark measurements.

No novelty, patentability, state-of-the-art, scientific-effect, benchmark-superiority, or performance-superiority claim is made.

`automatic_control_allowed`, `activation_allowed`, and `traffic_switching_allowed` remain false.

## Next evidence dependency

The next safe gate is **repeated local-host parent-forced child-termination containment with monotonic recovery across successive valid fencing generations**.

The evidence should run multiple independent spawn → stage incompatible uncommitted schema replacement → parent terminate → verify rollback/lock release cycles against the same SQLite database. After each terminated child, a valid fenced-resource successor mutation should advance the committed fencing/resource generation exactly once, stale/fresh read-only readers should expose only coherent committed pairs, no staging table should survive, and the next child crash cycle should begin from that new committed generation.

This gate is intended to test accumulation and recovery behavior across repeated exercised process failures. It must not be presented as soak testing, reliability-rate evidence, probabilistic availability, crash-proof operation, power-loss safety, distributed fault tolerance, HA/SLA evidence, production readiness, or performance evidence.
