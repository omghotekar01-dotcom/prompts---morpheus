# MORPHEUS Release Gate

Status: ACTIVE  
Purpose: make a release repeatable, inspectable, and difficult to overstate.

## Release principle

A MORPHEUS release is acceptable when the declared engineering gates pass on the exact release revision and all remaining limitations are explicit. A green release does not automatically mean publication acceptance, patentability, universal performance superiority, zero future defects, production certification, or native distributed hot swapping.

## Gate 0 — Source identity

Record:

- exact Git commit;
- release/tag name if used;
- repository cleanliness for the release builder;
- compiler/Python/Node/CMake versions used by the release validation;
- schema/protocol versions that changed since the previous release.

A release report without an exact source revision is incomplete.

## Gate 1 — Cross-platform CI

Required jobs:

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

- feature registry validates;
- no dependency cycles;
- research/blocked features cannot authorize automatic control;
- blocked features remain disabled;
- OpenAPI operation IDs are unique;
- critical API routes remain present;
- new semantic changes use versioned IR/schema/protocol identities;
- compatibility documentation is updated for breaking changes.

Reference: `docs/UPGRADE-AND-COMPATIBILITY.md`.

## Gate 3 — Workload/compiler correctness

Required:

- MWS validation tests;
- raw/resolved provenance tests;
- WorkloadIR canonical identity tests;
- ConfigurationIR identity tests;
- primitive manifest identity tests;
- generated artifact compilation where a compiler is available;
- schema-derived stateful differential verification;
- duplicate/mutation/graph route tests for supported generated operations.

Passing this gate establishes tested semantics for the covered cases, not mathematical proof for all inputs.

## Gate 4 — Core memory/runtime safety

Required:

- native C++ tests pass on Linux and Windows;
- ASan/UBSan gate passes on supported Linux CI;
- migration/version-slot concurrency tests report no invalid reads;
- stale reader leases preserve their snapshot/reference semantics;
- exact-generation/rollback guards remain enabled.

Additional deployment-specific race analysis may still be required beyond CI.

## Gate 5 — Adaptation transaction safety

Required:

- verified migration required before stage/commit;
- source/target/session identities rechecked before mutation;
- commit failure injection proves already-mutated local state is compensated;
- rollback preconditions are checked before mutation;
- wrong-session and duplicate rollback calls fail closed;
- evidence distinguishes local in-process coordination from cross-process replacement.

`native_cross_process_hot_swap` must remain blocked until separately implemented and validated.

## Gate 6 — Persistence/evidence integrity

Required:

- content-addressed artifacts re-hash successfully when read;
- evidence ledger hash chain verifies;
- corruption tests detect payload, previous-hash and forged-tail tampering;
- decision certificates retain source/config/evidence identity;
- release evidence package contains content hashes for included artifacts.

A hash chain provides tamper evidence for stored records; it is not an external timestamping/notarization service.

## Gate 7 — UI/startup resilience

Required:

- frontend production build succeeds;
- uploaded MORPHEUS identity mark remains usable in startup/sidebar/recovery presentation;
- startup progress is derived from real readiness requests rather than a fake timer;
- bounded read-only startup waits prevent indefinite blocking;
- critical backend failure offers retry/degraded workspace behavior;
- root React error boundary isolates render/lifecycle failures and offers recovery without implicit engine mutation.

## Gate 8 — Research truth boundary

Required:

- model predictions remain labeled predictions;
- machine-local exploratory measurements remain machine-local;
- held-out evaluator states when measurements are caller supplied;
- search regret against exhaustive model oracle is not called hardware regret;
- trace classifier/phase inference remains research-only until promotion criteria pass;
- synthetic classifier confusion matrix is packaged when that research surface is discussed;
- calibration mismatch/stale implementation evidence fails closed;
- negative or losing experimental outcomes are not discarded from research records.

## Gate 9 — Claim safety

The release must not make unsupported statements such as:

- “first ever” without a defensible prior-art review;
- “state of the art” without appropriately strong baselines and controlled evidence;
- “40% faster” without the exact experiment supporting that number;
- “patented/patentable” without the appropriate legal process;
- “production hot swap” when only local in-process routing is demonstrated;
- “zero bugs” or “error free forever.”

Claims should carry evidence references or be marked proposed/target/hypothesis.

## Gate 10 — Release artifacts

Minimum source release package:

- repository revision;
- release manifest;
- reproducibility/environment manifest;
- capability/feature maturity ledger;
- API contract fingerprint;
- test/CI status references;
- known limitations;
- research truth boundary;
- relevant generated example(s) where practical;
- license/notices required by included dependencies.

Large benchmark dumps and build products should remain outside Git and be referenced through content hashes/manifests.

## Release decision

Use only these outcomes:

- `PASS_ENGINEERING_RELEASE` — all required engineering gates for the declared scope pass on exact head.
- `PASS_WITH_KNOWN_LIMITATIONS` — gates pass but named non-blocking limitations remain.
- `BLOCKED` — at least one required gate is red, missing, or contradicted by evidence.

Never convert `BLOCKED` to a pass by changing wording alone.

## Definition of “100%” for internal engineering dashboards

If an internal dashboard reports `100%`, it may mean only **100% of its explicitly enumerated engineering gates passed**. The dashboard must also show excluded outcomes such as external publication review, customer pilots, legal patent review, controlled multi-machine performance campaigns, and unimplemented cross-process hot swap.

This prevents a useful engineering percentage from becoming a false universal completion claim.
