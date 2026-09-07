# MORPHEUS E13 Evolution Status Supplement

This supplement records the next verified post-E12 engineering gate without rewriting the established historical ledgers. The repository and exact verified CI head remain the source of truth.

Truth rule: this checkpoint records tested engineering behavior of a local filesystem-backed reference adapter only. It is not scientific measurement, production authorization, distributed-system proof, external-resource attestation, a benchmark result, or a novelty/performance claim.

---

## E13 — Local Durable Protected-Resource Fencing Restart Recovery

State: **ENGINEERING COMPLETE FOR LOCAL FILESYSTEM-BACKED REFERENCE-ADAPTER SCOPE**

Verified checkpoint: GitHub Actions run `34115345914` (run 1092), commit `254d2d79b2d8c4ed55f77cbb9da2d75c0a563df1`, MORPHEUS CI successful across Backend Ubuntu Python 3.11/3.14, Backend Windows Python 3.14 + MSVC, Core Ubuntu/Windows C++20, ASan+UBSan, and the React/TypeScript production build.

| Gate | State | Evidence boundary |
|---|---|---|
| E13.1 Exact persisted resource/authority identity | COMPLETE | one adapter is configured for one exact `(resource_id, fencing_authority_id)` pair and rejects persisted or requested identity drift before token acceptance |
| E13.2 Canonical high-water state encoding | COMPLETE | the local state record uses a fixed schema, exact integer version/counter types, deterministic canonical UTF-8 JSON, duplicate-key rejection, and exact post-decode canonical-byte verification |
| E13.3 Fail-closed restart recovery | COMPLETE | reconstructing an adapter from an existing valid state file reloads the highest accepted fencing generation; malformed, corrupted, noncanonical, schema-drifted or identity-drifted state fails before fencing-token use |
| E13.4 Restart-preserved stale/equal/new semantics | COMPLETE | after local restart, lower generations remain rejected, equal generations remain idempotently accepted without advancing state, and strictly newer generations advance the persisted high-water mark |
| E13.5 Pre-decision persisted-state revalidation | COMPLETE | the adapter re-reads and validates persisted state before each token decision, so tested external tampering after construction fails before a newer token can be accepted by that adapter |
| E13.6 Write-replace-reload ordering | COMPLETE | a strictly newer accepted generation is staged in the same directory, flushed and file-fsynced, installed with `os.replace`, then byte-for-byte re-read and fully decoded before the call returns success |
| E13.7 Replacement failure preservation | COMPLETE | injected pre-replacement failure leaves the previous target bytes intact and the adapter cleans its staged temporary file |
| E13.8 Post-replacement verification failure | COMPLETE | injected post-replacement byte drift is detected and the operation fails closed instead of returning an accepted decision |
| E13.9 E11 callback compatibility | COMPLETE | the adapter returns the established `ProtectedResourceFencingDecision` contract and can be supplied at the protected-resource fencing validation boundary |
| E13.10 No authority escalation | COMPLETE | automatic control, activation and traffic switching remain explicitly forbidden |

### E13 claim boundary

E13 supports the narrow engineering claim that MORPHEUS now contains a tested local filesystem-backed reference adapter that preserves one protected-resource fencing high-water generation across adapter reconstruction/restart and fails closed on the tested persisted-state corruption, schema, canonical-encoding, identity and replacement/reload failure cases.

The phrase **local durable** in this checkpoint means only that the tested state is persisted to a local filesystem record and recovered by a newly constructed adapter. It must not be interpreted as a proof of crash consistency or storage durability under arbitrary power loss, kernel failure, filesystem failure, hardware failure or adversarial storage behavior.

The adapter serializes transitions only between threads sharing that exact Python object. E13 does **not** establish or prove cross-process or multi-adapter mutual exclusion, compare-and-swap semantics, distributed linearizability, distributed atomicity, consensus, leases, distributed locking, distributed transactions, multi-receiver exclusion, or a globally current fencing generation. Two independently constructed adapters aimed at the same state path are outside this verified ordering model.

The tested `file fsync` + `os.replace` + exact reload sequence does not prove parent-directory persistence or power-loss durability and does not attest the operating system, filesystem, storage device or cloud volume. E13 also does not prove that an external database, service, filesystem resource, network target or other production protected resource actually enforces the recorded fencing generation.

E13 does not establish safe cutover, live process replacement, activation, automatic control, production traffic switching, availability, authentication, compromise resistance, HA/SLA behavior or production readiness.

No benchmark, latency, throughput, scaling, performance-superiority, novelty, patentability, state-of-the-art or scientific-effect claim is introduced by E13.

---

## Next evidence dependency

The next dependency-ready engineering gate should address the remaining local lost-update window rather than adding another receipt. A stronger local adapter contract should detect when the persisted fencing state changes between the adapter's verified read and attempted replacement, fail closed on that conflict, and provide deterministic evidence for stale/equal/new generations under independently constructed same-path adapter interleavings.

That gate should be framed as local conflict-detection/ordering evidence only unless an external store with an actual atomic conditional-write primitive is separately specified and tested. It must not be promoted into a distributed linearizability, consensus, lease, production-resource or safe-cutover claim without corresponding evidence.

MORPHEUS remains non-activating and non-traffic-switching at this boundary.

E2.B1 scientific execution also remains separately open: engineering CI does not substitute for the frozen non-CI measurement campaign defined by the main evolution ledger and RQ7 protocol.
