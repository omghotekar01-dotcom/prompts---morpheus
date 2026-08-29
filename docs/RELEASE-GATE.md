# MORPHEUS Release Gate

Status: ACTIVE  
Purpose: make a release repeatable, inspectable and difficult to overstate.

## Release principle
A MORPHEUS release is acceptable when the declared repository engineering gates pass on the exact release revision and all remaining limitations are explicit. A green repository release does **not** automatically mean publication acceptance, patentability/freedom-to-operate, universal performance superiority, independent replication, customer traction, security/regulatory certification or native distributed/cross-process hot swapping.

## Gate 0 — Source identity
Record:
- exact Git commit;
- release/tag name if used;
- repository cleanliness for the release builder;
- compiler/Python/Node/CMake versions used by release validation;
- schema/protocol versions changed since the previous release.

A release report without exact source revision is incomplete.

## Gate 1 — Cross-platform CI
Required jobs for the declared current support matrix:
- Backend / Ubuntu / Python 3.11;
- Backend / Ubuntu / Python 3.14;
- Backend / Windows / Python 3.14 + MSVC;
- Core / Ubuntu / C++20;
- Core / Windows / MSVC C++20;
- Core / ASan + UBSan;
- Frontend / React TypeScript production build.

All must pass on the release head. A green older commit does not certify a newer head.

## Gate 2 — Contract and upgrade safety
Required:
- feature registry validates and has a deterministic policy fingerprint;
- no dependency cycles;
- research/blocked features cannot authorize automatic control;
- blocked features remain disabled;
- OpenAPI operation IDs are unique;
- critical API routes remain present;
- API route-contract fingerprint is deterministic;
- new semantic changes use versioned IR/schema/protocol identities;
- compatibility documentation is updated for breaking changes.

Feature/API SHA-256 values are compatibility/provenance identities, not signatures or external attestations.

Reference: `docs/UPGRADE-AND-COMPATIBILITY.md`.

## Gate 3 — Workload/compiler correctness
Required:
- MWS validation tests;
- raw/resolved provenance tests;
- WorkloadIR canonical identity tests;
- ConfigurationIR identity tests;
- primitive implementation identity tests;
- generated artifact compilation where a compiler is available;
- schema-derived stateful differential verification;
- duplicate/mutation/graph route tests for supported generated operations.

Passing this gate establishes tested semantics for covered cases, not mathematical proof for all inputs.

## Gate 4 — Core memory/runtime safety
Required:
- native C++ tests pass on Linux and Windows;
- ASan/UBSan gate passes on supported Linux CI;
- migration/version-slot concurrency tests report no invalid reads;
- stale reader leases preserve documented snapshot/reference semantics;
- exact-generation/rollback guards remain enabled.

Deployment-specific race analysis may still be required beyond CI.

## Gate 5 — Adaptation transaction safety
Required:
- verified migration before stage/commit;
- source/target/session identities rechecked before mutation;
- commit failure injection proves already-mutated local state is compensated;
- rollback preconditions checked before mutation;
- wrong-session and duplicate rollback calls fail closed;
- evidence distinguishes local in-process coordination from cross-process replacement.

`native_cross_process_hot_swap` remains blocked until separately implemented and validated.

## Gate 6 — Persistence/evidence integrity
Required:
- content-addressed artifacts re-hash successfully when read;
- evidence ledger hash chain verifies;
- corruption tests detect payload, previous-hash and forged-tail tampering;
- decision certificates retain source/config/evidence identity;
- release evidence package contains content hashes for included artifacts.

A hash chain provides tamper evidence for stored records; it is not external timestamping/notarization.

## Gate 7 — UI/startup resilience
Required:
- frontend production build succeeds;
- MORPHEUS identity mark remains usable in startup/sidebar/recovery presentation;
- startup progress is derived from real readiness requests rather than a fake timer;
- bounded read-only startup waits prevent indefinite blocking;
- critical backend failure offers retry/degraded-workspace behavior;
- root React error boundary isolates render/lifecycle failures and offers recovery without implicit engine mutation.

## Gate 8 — Research truth boundary
Required:
- model predictions remain labeled predictions;
- machine-local exploratory measurements remain machine-local;
- held-out evaluator states when measurements are caller supplied;
- search regret against an exhaustive model oracle is not called hardware regret;
- trace classifier/phase inference remains research-only until promotion criteria pass;
- calibration mismatch/stale implementation/distribution/scale evidence fails closed;
- negative or losing experimental outcomes are retained.

## Gate 9 — Distribution-bound calibration provenance
Required when distribution-aware calibration evidence is packaged/claimed:
- raw calibration uses recognized distribution protocol;
- implementation, operation, scale and distribution identity are explicit;
- distribution-calibration matrix manifest is structurally validated;
- raw measurement and machine-profile hashes agree with the matrix manifest;
- standard-baseline statistics cannot be cross-paired with a different raw-measurement protocol;
- primitive-level calibration is not presented as end-to-end generated-candidate performance.

## Gate 10 — Claim safety
The release must not make unsupported statements such as:
- “first ever” without a defensible prior-art review;
- “state of the art” without appropriately strong baselines and controlled evidence;
- “40% faster” without the exact experiment supporting that number;
- “patented/patentable” without the appropriate legal process;
- “production hot swap” when only local in-process routing is demonstrated;
- “zero bugs”, “unhackable” or “error free forever.”

Claims should carry evidence references or be marked proposed/target/hypothesis.

## Gate 11 — Release/reproducibility artifacts
Minimum source release package:
- repository revision;
- release manifest;
- strict reproducibility/environment manifest;
- capability/feature maturity ledger;
- API-contract fingerprint;
- feature-policy fingerprint;
- test/CI status references;
- known limitations;
- research truth boundary;
- relevant generated example(s) where practical;
- license/notices required by included dependencies.

Strict reproducibility should bind exact source commit plus relevant evidence, API-contract and feature-policy identities. Hash identity is not independent scientific attestation or authorship signing.

Large benchmark dumps and build products should remain outside Git and be referenced through content hashes/manifests.

## Gate 12 — Canonical repository/corpus integrity
Required for repository-engineering completion:
- exactly 39 canonical Markdown prompt volumes exist under `prompts/`;
- `MASTER-INDEX.md` indexes all 39;
- prompt #30 is labeled Integration Checkpoint I rather than the final Bible;
- `prompts/39-grand-master-final.md` is the canonical final integration directive;
- README, AI-START-HERE, CORPUS-MANIFEST and FINAL-CHECKLIST point to #39 correctly;
- automated backend tests enforce these invariants;
- no repository completion claim is inferred from prompt file count alone.

## Release decision
Use only these outcomes:
- `PASS_ENGINEERING_RELEASE` — all required engineering gates for the declared scope pass on exact head.
- `PASS_WITH_KNOWN_LIMITATIONS` — gates pass but named non-blocking limitations remain.
- `BLOCKED` — at least one required gate is red, missing or contradicted by evidence.

Never convert `BLOCKED` to a pass by changing wording alone.

## Definition of “100%” for internal engineering dashboards
If an internal dashboard reports `100%`, it may mean only **100% of its explicitly enumerated repository engineering gates passed**. The dashboard/release notes must continue to show excluded outcomes such as external publication review, customer pilots, legal patent review, independent multi-machine performance campaigns, security/regulatory certification and unimplemented cross-process hot swap.

This keeps a useful engineering percentage from becoming a false universal-completion claim.