# MORPHEUS Evolution Status — E79

## Checkpoint

**E79 — Two duplicate groups conflicting at one same generation after staged-holder rollback**

This checkpoint records only evidence verified on exact implementation/test head `0bef99b5ce081196e5962b340dc4a2719e1c3659` by MORPHEUS CI run **1252** (`34393496937`), which completed successfully before this document was created.

## Verified capability

For the exercised local-host Python multiprocessing/SQLite path, MORPHEUS demonstrates bounded convergence when two logical duplicate groups conflict for one pending fencing generation after a controlled staged-holder rollback.

Four independently reconstructed production writers contend for one pending counter: two exact copies of mutation A and two exact copies of conflicting mutation B. While the staged transaction owns SQLite's write path, all four writers remain blocked and both long-lived and fresh readers expose only the preceding coherent committed fencing/resource pair.

After controlled holder termination, either logical mutation may win. The winning duplicate group converges through exactly one state-changing `applied` outcome and one non-state-changing `idempotent` outcome. Both writers in the losing logical group fail closed through `generation_reuse_rejected`. Exactly one fencing/resource generation is consumed.

The regression also derives the committed pair from the scheduler-selected winner and verifies paired one-step fencing/resource advancement, stale-generation rejection, repeated losing-mutation rejection, exact winner replay idempotency, reader convergence, SQLite write-lock release, later successor progress, and continued denial of automatic control, activation, and production traffic switching.

## Scientific and production truth boundary

E79 is deterministic bounded local-host SQLite multiprocessing evidence at controlled blocked-waiter and staged-but-uncommitted transaction boundaries. The process topology, staged transaction, mutation identities, and holder termination point are test-controlled. Which logical mutation wins is intentionally unspecified.

E79 does not establish deterministic scheduling or winner selection, arbitrary crash safety, power-loss durability, filesystem or storage recovery, distributed serializability or linearizability, distributed consensus, cross-host fencing, distributed exactly-once execution, network-partition correctness, HA/failover, fairness, starvation freedom, general liveness, latency or throughput guarantees, production readiness, security guarantees, benchmark superiority, reliability rates, novelty, patentability, or scientific effect.

`automatic_control_allowed`, `activation_allowed`, and `traffic_switching_allowed` remain false.

## Next evidence dependency

The next safe gate is **partial duplicate-group waiter loss before same-generation conflict recovery**.

Reconstruct two exact waiters for mutation A and two exact waiters for conflicting mutation B against one staged-but-uncommitted pending generation. While the holder is alive, prove all four remain blocked and readers remain on the preceding coherent committed pair. Deliberately terminate one waiter from each logical duplicate group while the holder still owns the SQLite write transaction, and prove those waiter losses do not mutate or expose the pending generation and do not terminate the holder.

Then terminate only the staged holder and allow the two surviving independently reconstructed waiters—one for A and one for B—to contend on the recovered write path. Permit either survivor to win, but require exactly one `applied` outcome and exactly one `generation_reuse_rejected` outcome, with exactly one fencing/resource generation consumed. Reconstruct an exact replay of the winning mutation afterward and require `idempotent` convergence; reconstruct the losing mutation afterward and require continued `generation_reuse_rejected` behavior.

Retain coherent reader convergence, paired one-step advancement, stale rejection, lock release, successor progress, and the existing false automatic-control/activation/traffic-switching flags.

This remains bounded local SQLite/process-loss evidence only and must not be described as arbitrary process-failure tolerance, distributed consensus, distributed exactly-once execution, deterministic winner selection, fairness, general liveness, production readiness, or performance superiority.
