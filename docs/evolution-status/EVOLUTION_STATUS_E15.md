# MORPHEUS E15 Evolution Status Supplement

This supplement records the verified post-E14 engineering gate without rewriting earlier ledgers. The repository and exact verified CI head remain the source of truth.

Truth rule: this checkpoint records tested local-host engineering behavior for cooperating MORPHEUS processes using a filesystem-backed reference adapter. It is not scientific measurement, distributed-system proof, production authorization, external-resource attestation, benchmark evidence, or a novelty/performance claim.

---

## E15 — Cooperative Local-Host Cross-Process Durable Fencing Exclusion

State: **ENGINEERING COMPLETE FOR COOPERATING MORPHEUS PROCESSES ON ONE LOCAL HOST / ONE CANONICAL STATE PATH**

Verified checkpoint: GitHub Actions run `34135898999` (run 1105), commit `759d5333d767f5fe784bc0b30ccb9e7b427871d1`, MORPHEUS CI successful for the exact head.

| Gate | State | Evidence boundary |
|---|---|---|
| E15.1 Canonical host-lock sidecar | COMPLETE | the durable adapter derives one canonical sidecar lock path from the canonical fencing-state path |
| E15.2 POSIX local-host exclusion | COMPLETE | cooperating processes use an exclusive `flock` around construction validation and each durable transition on supported POSIX CI |
| E15.3 Windows local-host exclusion | COMPLETE | cooperating processes use a one-byte `msvcrt` file-region lock around the same sequence on supported Windows CI |
| E15.4 Cross-process blocking/release | COMPLETE | multiprocessing evidence verifies a second cooperating process cannot acquire the same host lock until the holder releases it |
| E15.5 Process-abandonment release | COMPLETE | multiprocessing evidence verifies the chosen OS lock is released after the owning process exits while holding it in the tested crash/abandonment case |
| E15.6 Durable transition serialization | COMPLETE | separate cooperating processes targeting the same state path serialize durable fencing transitions through the host lock |
| E15.7 High-water semantics retained | COMPLETE | stale/equal/new generation behavior remains governed by the persisted high-water fencing generation across process boundaries |
| E15.8 Non-cooperating writer defense retained | COMPLETE | byte-identity conflict detection still fails closed when direct external file modification or deletion becomes visible between verified read and attempted replacement |
| E15.9 Existing canonical/restart protections retained | COMPLETE | canonical encoding, exact identity binding, corruption rejection, replacement-failure preservation and post-replace exact reload remain covered by cumulative CI |
| E15.10 No authority escalation | COMPLETE | automatic control, activation and traffic switching remain explicitly forbidden |

### E15 claim boundary

E15 supports only the narrow engineering claim that cooperating MORPHEUS processes on one local host, targeting the same canonical local fencing-state path and participating in the same sidecar-lock protocol, serialize the tested fencing transition sequence with the supported OS advisory locking primitives.

The lock is advisory. A non-cooperating process, external program, filesystem actor, or different host can ignore the sidecar protocol. The retained pre-replacement byte comparison detects only changes visible at the comparison point; it is not an atomic compare-and-swap primitive against non-participants.

E15 therefore does **not** establish distributed mutual exclusion, distributed linearizability, consensus, lease semantics, database conditional writes, filesystem transactionality, globally current fencing state, multi-host exclusion, multi-receiver safety, or safe production-resource fencing.

The local persistence sequence does not prove parent-directory persistence, arbitrary-crash consistency, power-loss durability, filesystem/storage-device correctness, availability, authentication, authorization, or compromise resistance. It also does not prove that any external protected database, service, device, filesystem resource or network target actually enforces the fencing generation.

E15 does not establish safe cutover, live process replacement, automatic control, activation, production traffic switching, HA/SLA behavior or production readiness.

No benchmark, latency, throughput, scale, performance-superiority, novelty, patentability, state-of-the-art or scientific-effect claim is introduced by E15.

---

## Next evidence dependency

The next dependency-ready gate should stop extending local advisory-lock semantics and introduce a narrow **atomic conditional-write backend contract** for protected-resource fencing state. The contract should make predecessor identity/version explicit and distinguish accepted transition, stale-token rejection, and compare-and-swap conflict without claiming a concrete external backend is correct before one is actually implemented and tested.

The reference implementation may use an in-memory atomic model solely to verify MORPHEUS-side state-machine and failure-ordering semantics. Any filesystem, database, cloud store or distributed backend must remain separately unverified until a concrete backend demonstrates its own atomic conditional-write behavior under corresponding evidence.

The gate should cover exact resource/authority identity binding, first/newer/equal/stale generation semantics, predecessor-version mismatch, retry-safe idempotence, malformed backend responses, backend exceptions, and explicit denial of activation/traffic switching. It must not relabel a caller-supplied callback as distributed consensus, linearizability, durability or production fencing.

MORPHEUS remains non-activating and non-traffic-switching at this boundary.

E2.B1 scientific execution also remains separately open: engineering CI does not substitute for the frozen non-CI measurement campaign defined by the main evolution ledger and RQ7 protocol.
