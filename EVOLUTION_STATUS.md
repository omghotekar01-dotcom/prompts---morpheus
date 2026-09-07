# MORPHEUS Post-Completion Evolution Status

This ledger is intentionally separate from `PHASE_STATUS.md` and the original P1–P12 engineering-completion report.

**Original MORPHEUS engineering program:** complete. Post-completion evolution does not reduce, renumber or retroactively redefine that completion state.

Truth rule: an evolution gate is marked complete only for the scope its evidence actually supports. Engineering infrastructure, CI smoke evidence, analysis tooling and real scientific measurements are separate states.

---

## E1 — Generated-Configuration Same-Process Migration

State: **ENGINEERING COMPLETE FOR DECLARED SAME-PROCESS SCOPE**

Verified core checkpoint: GitHub Actions run `33239729368` (run 495), commit `4031d2de4bbb03a0b72fcbbb82a087b733fca3f7`, all seven jobs successful including Linux, Windows/MSVC and sanitizer lanes.

| Gate | State | Evidence boundary |
|---|---|---|
| E1.1 Distinct generated C++ configurations coexist | COMPLETE | separate namespaces/configuration identities in one process |
| E1.2 Cross-type logical state reconstruction | COMPLETE | explicit record conversion through migration helpers |
| E1.3 Atomic type-erased validated publication | COMPLETE | generation-aware `ErasedVersionedSlot`; stale/ABA publication rejected |
| E1.4 Concurrent immutable-reader + health + rollback harness | COMPLETE | generated source/target harness; zero-invalid-reader invariant |
| E1.5 Cross-platform compile/run verifier | COMPLETE | exact generated harness verified under Linux and Windows/MSVC CI |
| E1.6 API, persistence and release claim evidence | COMPLETE IN IMPLEMENTATION | generated bundle/verify API, content-addressed artifacts, strict `same_process_generated_migration` release role |

### E1 claim boundary

E1 supports the narrow claim that a provenance-bound pair of generated configurations can complete logical-state transfer, shadow validation, atomic same-process publication, concurrent immutable-reader checks, health gating and rollback on the verified local toolchain scope.

E1 does **not** establish concurrent-writer migration, native cross-process/distributed replacement, production availability, SLA behavior or performance superiority.

---

## E2 — Generated Migration Measurement Campaign

State: **RESEARCH TOOLING IMPLEMENTED; REAL SCIENTIFIC EXECUTION OPEN**

The engineering/tooling path remains covered by the repository CI matrix. A green CI run is engineering verification only; it is not scientific measurement and cannot satisfy the open E2-B campaign gates.

### E2-A — Measurement, analysis and evidence infrastructure

| Gate | State | Implementation / boundary |
|---|---|---|
| E2.A1 Benchmark actual generated source/target pair | COMPLETE | `backend/app/generated_migration_benchmark.py` |
| E2.A2 Fail-closed benchmark evidence validation | COMPLETE | strict schema/protocol/provenance and reader-safety verification |
| E2.A3 Frozen experiment matrix | COMPLETE | `research/matrices/rq7-generated-migration.json`; 24 factor cells × 10 repetitions |
| E2.A4 Deterministic campaign executor + descriptive summary | COMPLETE | compile-once prepared benchmark session; frozen-order campaign output |
| E2.A5 Machine/toolchain identity binding | COMPLETE | `morpheus-machine-profile-v2`; benchmark compiler must match captured profile |
| E2.A6 Atomic checkpoint/resume | COMPLETE | report/factor/campaign/machine/compiler hashes validated; failed prior cells never silently replaced; zero-work resume supported |
| E2.A7 Measurement-environment provenance | COMPLETE | start/end affinity, CPU-count, governor/power, load/frequency/thermal metadata when observable; nested semantics and coverage validated; metadata is not control proof |
| E2.A8 Complete-local transition-cost attestation | COMPLETE IN IMPLEMENTATION | CI/partial/mixed campaigns cannot mint `generated_migration_transition_cost_evidence` |
| E2.A9 H7-v1 confirmatory analysis | COMPLETE IN IMPLEMENTATION | cell medians + matched blocks; deterministic bootstrap; exact sign tests; Holm reader family; descriptive residual model |
| E2.A10 Exact H7 analysis implementation provenance | COMPLETE IN IMPLEMENTATION | exact analysis-source byte SHA plus recorded Python runtime identity |
| E2.A11 Positive-result-only H7 effect attestation | COMPLETE IN IMPLEMENTATION | `rq7_record_count_effect_evidence` cannot be minted for `NOT_FULLY_CONFIRMED`, resumed/partial environment coverage or insufficient observable stability |
| E2.A12 Deterministic finalization/package pipeline | COMPLETE IN IMPLEMENTATION | one-command offline finalizer preserves positive and negative H7 outcomes; release package enforces unique roles and H7 cross-artifact identity |

### E2-B — Scientific execution

| Gate | State | Acceptance requirement |
|---|---|---|
| E2.B1 Fresh controlled local RQ7 campaign | **OPEN** | one non-CI invocation; all 24 frozen cells × 10 repetitions; zero invalid reads; matching machine/toolchain; full environment coverage |
| E2.B2 Apply frozen H7-v1 to real E2.B1 evidence | **TOOLING COMPLETE; RESULT PENDING E2.B1** | run the unchanged finalizer/analysis on the real campaign and preserve `SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE` or `NOT_FULLY_CONFIRMED` exactly as produced |
| E2.B3 External-validity replication | **OPEN** | additional declared hardware/toolchain campaigns before cross-machine/general claims |

Canonical scientific protocol: `research/RQ7-GENERATED-MIGRATION-PROTOCOL.md`.

### E2 claim boundary

A full GitHub Actions execution is **CI smoke evidence**, not paper-grade transition-cost evidence. The role `generated_migration_transition_cost_evidence` is mintable only by a complete homogeneous non-CI local campaign and supports only measured transition costs for the frozen matrix on its declared machine/toolchain.

The positive claim `rq7_systematic_record_count_effect` is stricter: it also requires the frozen H7 analysis, exact analysis source/runtime provenance, one-invocation qualifying environment metadata and the positive-result-only `rq7_record_count_effect_evidence` attestation. An unconfirmed H7 outcome remains valid scientific evidence but cannot satisfy the positive claim gate.

No asymptotic scaling-law, performance-superiority or cross-machine claim is authorized by E2. Cross-machine generalization remains blocked until E2.B3.

---

## E3 — Portable Logical Generated-Index Process Transfer

State: **ENGINEERING COMPLETE FOR VERIFIED LOGICAL-HANDOFF / RECEIPT-REPLAY SCOPE**

Verified checkpoint: GitHub Actions run `34051060396` (run 1038), commit `357b0f3d44b948f14872b792ce786dc40caea692`, all seven jobs successful across Backend Ubuntu Python 3.11/3.14, Backend Windows Python 3.14 + MSVC, Core Ubuntu/Windows C++20, ASan+UBSan and the React/TypeScript production build.

| Gate | State | Evidence boundary |
|---|---|---|
| E3.1 Portable generated-index logical snapshot | COMPLETE | record-level logical state is encoded through caller-supplied codecs; no native-memory persistence claim |
| E3.2 Cross-candidate process recovery harness | COMPLETE | distinct generated physical candidates reconstruct equivalent logical state in separate processes under tested fixtures |
| E3.3 Cross-platform process-recovery verification | COMPLETE | Linux and native Windows/MSVC backend/core paths are exercised by CI |
| E3.4 Schema + codec identity-bound envelope | COMPLETE | exact opaque logical schema and record-codec identities are checked before record decoding |
| E3.5 Generated-record schema identity binding | COMPLETE | source/target generated record schemas must match the canonical generated schema identity |
| E3.6 Non-activating verified process-transfer admission | COMPLETE | exact inspected snapshot bytes are bound to a previously compile/correctness-verified migration and target artifact/verification-manifest identities |
| E3.7 C++/Python wire interoperability + malformed framing rejection | COMPLETE | emitted C++ bytes are parsed by the Python control plane and malformed envelope framing is rejected fail-closed |
| E3.8 Canonical process-transfer admission receipt replay | COMPLETE | strict canonical JSON receipt replays against exact snapshot bytes plus caller-supplied migration/session/target/artifact/manifest identities; authority flags remain false |

### E3 claim boundary

E3 supports the narrow engineering claim that MORPHEUS can serialize generated-index **logical record state**, bind it to exact schema/codec identities, reconstruct it across tested process boundaries, admit that handoff only after existing migration verification, and emit/replay a deterministic non-authoritative receipt tied to exact snapshot and target evidence identities.

E3 does **not** establish native object or address-space persistence, live process replacement, concurrent-writer cutover, distributed atomicity, freshness/authenticity of a receipt, rollback prevention, trusted monotonic head state, leases/fencing/consensus, crash/power-loss durability, HA/SLA behavior, production authorization or performance superiority. The receipt is evidence binding, not activation authority: `automatic_control_allowed` and `activation_allowed` remain false.

No benchmark, latency, throughput, scaling, novelty, patentability or scientific-effect claim is introduced by E3.

---

## E4 — Receiver-Side Verified Process-Transfer Evidence Persistence

State: **ENGINEERING COMPLETE FOR VERIFIED LOCAL FILE-PERSISTENCE / RELOAD SCOPE**

Verified checkpoint: GitHub Actions run `34054200224` (run 1042), commit `3aab9d1df2595065be6cd6fadcb3a2bb765a520d`, all seven jobs successful across Backend Ubuntu Python 3.11/3.14, Backend Windows Python 3.14 + MSVC, Core Ubuntu/Windows C++20, ASan+UBSan and the React/TypeScript production build.

| Gate | State | Evidence boundary |
|---|---|---|
| E4.1 Deterministic verified receipt+snapshot bundle | COMPLETE | exact canonical receipt and exact identified logical snapshot are re-verified before deterministic length-framed bundling |
| E4.2 Fail-closed persisted-bundle verification | COMPLETE | malformed framing, trailing bytes, snapshot tampering and expected-identity drift are rejected before evidence is accepted |
| E4.3 Receiver-side staged persistence + reload verification | COMPLETE | same-directory temporary file, file-level `fsync`, `os.replace`, byte-for-byte re-read and full receipt/snapshot replay verified on repository CI platforms |
| E4.4 Pre-write failure preserves prior target + no authority escalation | COMPLETE | failed evidence verification occurs before target replacement; persistence evidence keeps `automatic_control_allowed=false` and `activation_allowed=false` |

### E4 claim boundary

E4 supports the narrow engineering claim that MORPHEUS can persist an **already admitted, non-authoritative logical process-transfer evidence bundle** to a local receiver filesystem and re-verify the exact persisted bytes against the declared migration/session/target/schema/codec/artifact/manifest identities before treating that file as verified evidence.

E4 does **not** establish receipt authenticity or freshness, trusted latest-head state, rollback/replay prevention, a trusted monotonic counter, multi-writer serialization, adversarial-filesystem isolation, directory-entry persistence, power-loss/crash durability, live process replacement, activation authorization, fencing/leases/consensus, HA/SLA behavior or production authorization. `fsync` + `os.replace` are recorded implementation steps, not a claim of power-loss-safe durable storage on every filesystem/platform.

No benchmark, latency, throughput, scaling, novelty, patentability or scientific-effect claim is introduced by E4.

---

## E5 — Cooperative Local Monotonic Process-Transfer Head

State: **ENGINEERING COMPLETE FOR VERIFIED SINGLE-RECEIVER / COOPERATIVE-WRITER ORDERING SCOPE**

Verified checkpoint: GitHub Actions run `34057147241` (run 1044), commit `d803aadd2e96fc4e2fa0f5b75b805a926467c91c`, all seven jobs successful across Backend Ubuntu Python 3.11/3.14, Backend Windows Python 3.14 + MSVC, Core Ubuntu/Windows C++20, ASan+UBSan and the React/TypeScript production build.

| Gate | State | Evidence boundary |
|---|---|---|
| E5.1 Canonical local head record | COMPLETE | strict canonical JSON binds authority label, contiguous sequence, prior-head SHA-256, verified bundle SHA-256 and migration/session/target identities |
| E5.2 Genesis + contiguous monotonic sequence checks | COMPLETE | initial sequence must be 1 from a fixed genesis hash; replayed or skipped sequence numbers are rejected before replacement |
| E5.3 Explicit stale-head compare-and-swap rejection | COMPLETE | caller must present the exact hash of the currently persisted canonical head before advancing it |
| E5.4 Verified-bundle binding before head advancement | COMPLETE | candidate head is not written until the referenced persisted transfer bundle passes the existing receipt/snapshot identity verification boundary |
| E5.5 Staged replacement + post-write canonical re-verification | COMPLETE | same-directory temporary file, file-level `fsync`, `os.replace`, reload, canonical parse and exact head-hash verification are exercised on repository CI platforms |
| E5.6 No activation-authority escalation | COMPLETE | returned head evidence keeps `automatic_control_allowed=false` and `activation_allowed=false` |

### E5 claim boundary

E5 supports the narrow engineering claim that, for a cooperative single-receiver local workflow, MORPHEUS can maintain a canonical hash-chained process-transfer evidence head, reject stale compare-and-swap expectations, reject sequence replay/gaps, and bind each accepted head advancement to an already verified persisted transfer bundle.

E5 does **not** authenticate the authority identifier, protect against an adversary able to rewrite local head storage, serialize truly concurrent writers across processes, provide a trusted hardware/remote monotonic counter, guarantee crash/power-loss durability, prove global freshness, establish leases/fencing/consensus, perform live process replacement, or authorize activation/automatic control. It therefore is not a distributed or adversarial rollback-prevention claim.

No benchmark, latency, throughput, scaling, novelty, patentability, scientific-effect, HA/SLA or production-readiness claim is introduced by E5.

---

## E6 — Cooperative Local Restart-Time Transfer Evidence Verification

State: **ENGINEERING COMPLETE FOR VERIFIED LOCAL COOPERATIVE-WRITER / RESTART-CONSISTENCY SCOPE**

Verified checkpoint: GitHub Actions run `34063434886` (run 1049), commit `f8adfeef21d171817fe0335b67e530a993f72b35`, all seven jobs successful across Backend Ubuntu Python 3.11/3.14, Backend Windows Python 3.14 + MSVC, Core Ubuntu/Windows C++20, ASan+UBSan and the React/TypeScript production build.

| Gate | State | Evidence boundary |
|---|---|---|
| E6.1 Cooperative local head-writer exclusion | COMPLETE | atomic exclusive lock-file creation surrounds head read/CAS/evidence verification/staged replacement; a cooperating concurrent writer fails closed while the lock exists |
| E6.2 Orphan-lock non-inference + failure cleanup | COMPLETE | existing locks are neither deleted nor guessed stale; controlled verification and replacement failures release only the caller-owned lock and remove staged temporary files |
| E6.3 Exact restart-head expectation | COMPLETE | restart verification requires the exact caller-supplied canonical head SHA-256 plus authority label, sequence and migration/session/target identities |
| E6.4 Restart-time persisted-bundle replay and binding | COMPLETE | the supplied persisted receipt/snapshot bundle is fully re-verified and its exact bundle SHA-256 must match the canonical head binding |
| E6.5 Cooperative writer exclusion during restart verification | COMPLETE | restart re-verification holds the same local cooperative exclusion mechanism so cooperating head writers cannot advance the head during the check |
| E6.6 Read-only restart evidence with no authority escalation | COMPLETE | verified restart leaves head and bundle bytes unchanged and keeps `automatic_control_allowed=false` and `activation_allowed=false` |

### E6 claim boundary

E6 supports the narrow engineering claim that a MORPHEUS receiver can, under the tested cooperative local-filesystem model, exclude cooperating head writers while advancing or restart-checking the local process-transfer head and can re-establish read-only consistency between an exact caller-expected canonical head and the exact persisted evidence bundle bound by that head.

E6 does **not** prove that the caller-supplied expected head is globally fresh or independently trusted, authenticate the authority or lock owner, recover crashed-owner/orphaned locks, resist processes that ignore/delete the lock or adversarially rewrite local storage, establish distributed/shared-filesystem locking semantics, provide a trusted monotonic counter, guarantee crash/power-loss durability, establish consensus/fencing/leases, perform live process replacement, or authorize activation/automatic control.

No benchmark, latency, throughput, scaling, novelty, patentability, scientific-effect, HA/SLA or production-readiness claim is introduced by E6.

---

## E7 — Out-of-Band Secret Authenticated Restart Expectation

State: **ENGINEERING COMPLETE FOR VERIFIED AUTHENTICATED-EXPECTATION / LOCAL RESTART-REPLAY SCOPE**

Verified checkpoint: GitHub Actions run `34066188567` (run 1052), commit `f0a486071d8d803b629eed06dcfd6332790d73bd`, all seven jobs successful across Backend Ubuntu Python 3.11/3.14, Backend Windows Python 3.14 + MSVC, Core Ubuntu/Windows C++20, ASan+UBSan and the React/TypeScript production build.

| Gate | State | Evidence boundary |
|---|---|---|
| E7.1 Canonical authenticated restart statement | COMPLETE | deterministic statement binds protocol version, key identifier, authority identifier, sequence and exact canonical head SHA-256 |
| E7.2 HMAC-SHA256 verification with minimum secret length | COMPLETE | caller-provisioned byte secret must be at least 32 bytes; verification uses constant-time `hmac.compare_digest` on lowercase HMAC-SHA256 tags |
| E7.3 Authentication-before-local-restart replay | COMPLETE | wrong secret or authenticated-statement drift fails before entering the local restart/head verification path |
| E7.4 Composition with exact persisted head + bundle verification | COMPLETE | only an authenticated exact expectation proceeds into E6's canonical head, cooperative lock and persisted evidence-bundle replay checks |
| E7.5 Explicit replay/non-freshness evidence boundary | COMPLETE | tests intentionally show the same valid authentication tag can be reused for the same unchanged head; the gate therefore makes no freshness or anti-replay claim |
| E7.6 No activation-authority escalation | COMPLETE | authenticated restart evidence keeps `automatic_control_allowed=false` and `activation_allowed=false` |

### E7 claim boundary

E7 supports the narrow engineering claim that MORPHEUS can require possession of a caller-provisioned out-of-band secret before accepting a specific expected receiver authority/sequence/head tuple for local restart evidence replay, and can then compose that authentication result with E6's exact persisted-head and evidence-bundle verification.

E7 does **not** store, provision, rotate, revoke, attest or independently trust the secret or key identifier; establish freshness or anti-replay; provide a trusted hardware/remote monotonic counter; prevent rollback by an adversary controlling local storage; authenticate a lock owner; establish fencing, leases, consensus, distributed locking, crash/power-loss durability, live process replacement, production traffic switching, activation authority or automatic control. Reusing the same valid tag for the same unchanged head is deliberately permitted and tested, so E7 must not be represented as rollback-resistant or globally fresh authentication.

No benchmark, latency, throughput, scaling, novelty, patentability, scientific-effect, HA/SLA or production-readiness claim is introduced by E7.

---

## E8 — External Monotonic Restart Freshness Binding

State: **ENGINEERING COMPLETE FOR CALLER-SUPPLIED EXTERNAL-COUNTER BINDING / LOCAL RESTART-REPLAY SCOPE**

Verified checkpoint: GitHub Actions run `34069161819` (run 1056), commit `05c9dc706f5dd1c7fd9100da5d655a38a9546cc3`, all seven jobs successful across Backend Ubuntu Python 3.11/3.14, Backend Windows Python 3.14 + MSVC, Core Ubuntu/Windows C++20, ASan+UBSan and the React/TypeScript production build.

| Gate | State | Evidence boundary |
|---|---|---|
| E8.1 Freshness-coordinate authenticated statement | COMPLETE | a separate deterministic HMAC statement binds protocol version, key id, receiver authority/sequence/head plus caller-named freshness-authority identity and non-negative monotonic counter |
| E8.2 Exact external-counter observation before restart replay | COMPLETE | caller-supplied resolver must report the exact authenticated counter for the declared freshness authority before E6 local restart evidence verification runs |
| E8.3 Stale replay rejection after independent counter advance | COMPLETE | an authenticated expectation whose counter is lower than the resolver's current counter fails closed before persisted local restart replay |
| E8.4 Ahead/inconsistent counter rejection | COMPLETE | an authenticated expectation whose counter is greater than the resolver's current counter also fails closed rather than guessing authority state |
| E8.5 Resolver failure and malformed-counter rejection | COMPLETE | resolver exceptions, booleans, negative values and other invalid counter values are rejected without converting them into freshness evidence |
| E8.6 Authentication-before-freshness lookup and no authority escalation | COMPLETE | authenticated-statement drift fails before consulting the external resolver; successful evidence keeps `automatic_control_allowed=false` and `activation_allowed=false` |

### E8 claim boundary

E8 supports the narrow engineering claim that MORPHEUS can bind a restart expectation to a caller-supplied external monotonic freshness coordinate, authenticate that complete statement, require the external resolver to report the exact same current counter, and reject replay of an older authenticated counter after that independent source has advanced before proceeding into the existing local restart evidence gate.

E8 does **not** implement, authenticate, provision, persist, replicate or attest the external freshness authority or resolver; prove resolver liveness, correctness, atomicity or compromise resistance; establish global freshness or an end-to-end adversarial rollback guarantee; provide consensus, fencing, leases, distributed locking, crash/power-loss durability, live process replacement, production traffic switching, activation authority or automatic control. The freshness property is conditional on the independently supplied authority behaving according to its declared monotonic contract.

No benchmark, latency, throughput, scaling, novelty, patentability, scientific-effect, HA/SLA or production-readiness claim is introduced by E8.

---

## E9 — External Fencing Compare-and-Advance Restart Orchestration

State: **ENGINEERING COMPLETE FOR VERIFIED CALLER-SUPPLIED FENCING-CLAIM ORCHESTRATION / LOCAL RESTART-REPLAY SCOPE**

Verified checkpoint: GitHub Actions run `34075267540` (run 1060), commit `55cb14128c4770e7870dd780b570a108826731fc`, all seven jobs successful across Backend Ubuntu Python 3.11/3.14, Backend Windows Python 3.14 + MSVC, Core Ubuntu/Windows C++20, ASan+UBSan and the React/TypeScript production build.

| Gate | State | Evidence boundary |
|---|---|---|
| E9.1 Authenticated compare-and-advance statement | COMPLETE | deterministic HMAC statement binds key id, receiver authority/sequence/head, fencing-authority identity, exact previous fencing counter and immediately next requested counter |
| E9.2 Strict contiguous fencing-generation request | COMPLETE | requested fencing counter must equal previous counter + 1; gaps and malformed counters fail before external claim invocation |
| E9.3 Authentication-before-external fencing mutation | COMPLETE | statement drift fails before the caller-supplied compare-and-advance callback is invoked |
| E9.4 Exact external compare-and-advance response gate | COMPLETE | callback errors, malformed returns and any returned counter other than the exact requested next generation fail before local restart replay |
| E9.5 External-claim-before-local exact restart replay | COMPLETE | only a verified returned fencing generation proceeds into the existing exact persisted-head and evidence-bundle restart verification path |
| E9.6 Partial-failure semantics are explicit | COMPLETE | if local restart replay fails after an external claim, MORPHEUS does not attempt to decrement/roll back the external generation and still grants no activation, automatic-control or traffic-switching authority |

### E9 claim boundary

E9 supports the narrow engineering claim that MORPHEUS can authenticate one exact external fencing compare-and-advance request, require a caller-supplied operation to report the immediately next fencing generation, reject malformed/stale/inconsistent claim outcomes before local restart evidence is accepted, and then re-run the existing exact persisted restart evidence gate.

E9 does **not** implement or independently trust the external fencing authority; prove that the callback is atomic, linearizable, durable, available or compromise-resistant; prove multi-receiver exclusion or safe distributed cutover; establish leases, consensus, distributed locking, crash/power-loss durability, live process replacement, production traffic switching, activation authority or automatic control. A returned generation is evidence of the caller-supplied authority response only. Failed local replay after an external claim may consume that generation and is deliberately not rolled back.

No benchmark, latency, throughput, scaling, novelty, patentability, scientific-effect, HA/SLA or production-readiness claim is introduced by E9.

---

## Next evolution sequence

1. Keep the exact `main` head green across Linux/Windows Python, Linux/Windows C++20, frontend and sanitizer lanes; fix any red lane before promoting another checkpoint.
2. Preserve E9's trust boundary: stronger safe multi-receiver cutover requires integration with an actually trusted/independently specified fencing authority plus explicit atomicity, token-consumer and failure semantics; MORPHEUS's callback-contract verification alone does not prove those properties.
3. Execute E2.B1 once on a fresh controlled non-CI measurement machine without tuning the frozen matrix after observing timings.
4. Run `scripts/finalize_rq7_evidence.py` over that preserved run directory; retain the complete output whether H7 is supported or not.
5. If H7 is unconfirmed, report the negative/ambiguous result and do not alter the frozen protocol to manufacture a positive claim.
6. Replicate on additional declared hardware/toolchains before any external-validity statement.

This file tracks evolution state only. It does not claim publication acceptance, patentability, state-of-the-art performance or production readiness.