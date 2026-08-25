# MASTER PROMPT #20 — V18: VERIFICATION, TESTING, CI/CD & QUALITY ENGINEERING

Make correctness a first-class scientific property. MORPHEUS generates executable data structures; a fast wrong design is invalid.

## Test pyramid
Unit: MWS/IR, capability algebra, cost equations, search operators, codegen helpers. Property tests: randomized workloads/configurations and invariants. Differential tests: generated structure vs trusted reference semantics. Integration: parser -> search -> codegen -> compile -> execute. End-to-end: UI/API/worker/artifact. Performance tests are separate from correctness.

## Generated-code oracle
For each operation generate equivalent reference behavior using a simple trustworthy container/model. Feed identical deterministic operation sequences to candidate and oracle; compare return values, membership, result sets/order where specified and final logical dataset state.

## Stateful testing
Generate insert/delete/modify/query sequences including missing keys, duplicates according to schema, boundary ranges, empty/full datasets, long prefixes and structure rebuilds. Verify all secondary structures remain synchronized.

## Search verification
On tiny design spaces compare optimized/pruned search to exhaustive enumeration. Assert no feasible candidate is incorrectly discarded by any pruning rule claimed safe. Heuristic pruning must be labeled and evaluated rather than asserted safe.

## Cost model
Golden formula tests plus empirical regression tests. Ensure predicted values carry model version/uncertainty and cannot be serialized as measured values.

## Determinism
Fixed MWS + machine profile + model + seed + registry must produce same resolved IR and deterministic search decisions except explicitly measured noisy ranking stages. Hashes/manifests must be stable.

## Fuzz/security
Fuzz YAML/JSON, MWS semantics, trace parsers, generated identifiers and APIs. Test traversal, injection, archive bombs, malformed profiles, resource exhaustion and sandbox escapes at interfaces.

## Compatibility
Maintain fixtures for supported MWS/API/IR versions. Migration tests prove old persisted specs either migrate correctly or fail with explicit version error.

## CI lanes
PR-fast: formatting/lint/type/unit/schema/golden. PR-full: integration, generated-code differential, security. Main: end-to-end and stable microbenchmarks. Scheduled: broad fuzzing/calibration/performance/research replication. Keep flaky performance tests out of correctness gating unless statistically robust.

## Coverage
Measure code/branch coverage but prioritize semantic coverage matrix: data types x operations x primitive x update pattern x edge condition. Track unsupported combinations explicitly.

## Release gate
No release if golden synthesis changes without reviewed reason; generated code fails sanitizers; schema examples fail; migrations fail; reproducibility manifest differs unexpectedly; critical security issue exists.

## Deliverable
Implement test architecture, fixtures, generators, oracle, differential harness, property/fuzz tests, exhaustive-search checks, compatibility suite, CI workflows, quality dashboard and release checklist. Every bug found in production/research becomes a regression test.
