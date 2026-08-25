# MASTER PROMPT #24 — V22: EXTENSIBILITY, PLUGINS, SDK, PRIMITIVE ECOSYSTEM & GOVERNANCE

Design MORPHEUS so new physical structures, cost models and target backends can be added without turning the optimizer into a conditional jungle.

## Extension boundaries
Define typed interfaces for PrimitiveProvider, CostModelProvider, SearchStrategy, CodegenBackend, MachineProfiler and WorkloadImporter. Core IR/schema contracts are stable; extensions declare compatible versions/capabilities.

## Primitive manifest
Each primitive declares ID/version/license, supported key/value types, logical operations, ordering, uniqueness/null assumptions, mutation support, parameter schema, composition role, memory/build characteristics, calibration requirements, codegen implementation and test suite.

## Capability algebra
Compatibility is computed from declared capabilities and configuration constraints—not names. Search queries registry for structures satisfying required operations. Unsupported combinations are rejected before code generation.

## Provider trust
Start with in-tree trusted providers. External plugins later require package signing/checksums, explicit install, permission declaration and sandboxed calibration/build where feasible. Never dynamically execute arbitrary plugin code in the API process.

## SDK
Offer strongly typed Python API for orchestration/spec construction and stable JSON/HTTP API. Generated C++ library interface remains independent. Version SDK against API contracts.

## Registry
Local registry stores manifests and provider versions. Optional remote catalog may distribute metadata/packages later. Lock files pin exact providers to preserve reproducibility.

## Conformance
Every primitive must pass schema validation, reference differential tests, mutation consistency, sanitizer tests, benchmark smoke tests and deterministic manifest generation before registration. Performance superiority is not required; correctness is.

## Contribution governance
Require design proposal for changes to MWS/IR semantics; normal PR for isolated primitive additions. Maintain compatibility/deprecation policy, security disclosure process and code ownership for critical compiler/sandbox paths.

## Research extensions
Experimental providers are explicitly marked and cannot silently enter default production search. Experiments record their commit/version.

## Deliverable
Implement extension interfaces, primitive manifest schema, registry/locking, conformance harness, example third-party primitive, SDK contracts, compatibility policy, contributor workflow and security model. Extensibility must increase research velocity without sacrificing determinism.
