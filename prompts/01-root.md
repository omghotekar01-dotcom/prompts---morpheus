# MASTER PROMPT #1 — MORPHEUS ROOT ARCHITECTURE

Build MORPHEUS as a workload-aware, hardware-aware physical data-structure synthesis system. This file defines the complete program boundary and how all later volumes relate.

## Mission
Users describe data, logical operations, rates/weights, distributions, updates, resource constraints and optimization goals. MORPHEUS converts that intent into a validated workload contract, explores compatible physical structures/compositions, predicts and measures cost on the target machine, generates executable code, verifies correctness and can later re-evaluate the design when workload changes.

## Core layers
1. Input/specification: NL/form/YAML/JSON.
2. MWS validation/resolution.
3. WorkloadIR.
4. Primitive registry + capability algebra.
5. Machine profile + calibration.
6. Cost model + uncertainty.
7. Candidate generation/search/Pareto.
8. ConfigurationIR.
9. Code generation + compilation.
10. Differential correctness.
11. Benchmarking + provenance.
12. Runtime telemetry/adaptation.
13. Control plane/API/UI.
14. AI copilot as optional interface.
15. Research, patent, product and release systems.

## Non-negotiable invariants
Correctness before speed; measured != predicted; hard constraints never silently relaxed; unsupported features fail explicitly; workload intent stays independent from physical choice; every major result is versioned/hashed; search is checked against exhaustive tiny spaces; generated binaries run isolated; AI never overrides deterministic truth; claims never exceed evidence.

## Engineering philosophy
Prefer a small real vertical slice over broad mock functionality. Keep Git text-first and lightweight. Separate source-of-truth contracts from generated artifacts. Use typed data models, explicit state machines, deterministic serialization and reproducible experiment manifests.

## First proof
A minimal credible MORPHEUS must accept a workload with point/range/update operations, evaluate a small set of real primitives, search configurations under memory/latency objectives, generate C++20, pass differential tests and benchmark against strong baselines.

## Relationship to later volumes
Volumes 0–27 specialize constitution, research foundations, prior art, theory, MWS, IR, primitives, cost model, search, codegen, adaptation, backend, UI, AI, benchmarking, research, IP, production, testing, product, docs, demo, ecosystem, roadmap, architecture, autonomous build, audit and release. Prompt #30 integrates all of them.

# END MASTER PROMPT #1
