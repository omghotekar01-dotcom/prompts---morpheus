# MASTER PROMPT #1 — MORPHEUS ROOT ARCHITECTURE

Build MORPHEUS as a workload-aware, hardware-aware physical data-structure synthesis system. This file defines the program boundary and how the canonical 39-prompt Engineering Bible relates.

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
8. ConfigurationIR and composite ownership/routing.
9. Code generation + compilation.
10. Differential correctness.
11. Benchmarking + provenance.
12. Runtime telemetry/adaptation.
13. Control plane/API/UI.
14. AI copilot as optional interface.
15. Security, portability and hardware-aware systems concerns.
16. Research, patent, product and release systems.
17. Contract/test/continuity governance.

## Non-negotiable invariants
Correctness before speed; measured != predicted; hard constraints never silently relaxed; unsupported features fail explicitly; workload intent stays independent from physical choice; every major result is versioned/hashed; search is checked against exhaustive tiny spaces; generated binaries are untrusted until verified; AI never overrides deterministic truth; claims never exceed evidence.

## Engineering philosophy
Prefer a small real vertical slice over broad mock functionality. Keep Git text-first and lightweight. Separate source-of-truth contracts from generated artifacts. Use typed data models, explicit state machines, deterministic serialization and reproducible experiment manifests.

## First proof
A minimal credible MORPHEUS must accept a workload with point/range/update operations, evaluate a small set of real primitives, search configurations under memory/latency objectives, generate C++20, pass differential tests and benchmark against strong baselines.

## Relationship to the 39-prompt corpus
- Prompts #2–#29 define the original foundational, synthesis, platform, research, product and release domains.
- Prompt #30 is the **first integration checkpoint** retained for history and compatibility. It is not the final corpus directive.
- Prompts #31–#38 deepen security, portability, hardware awareness, advanced primitives, composite synthesis, distributed/edge frontiers, mathematics/algorithms and contract/test continuity.
- Prompt #39 (`prompts/39-grand-master-final.md`) is the **canonical final integration and implementation directive**.

When prose conflicts with tested/versioned executable contracts, tested code and normative schemas remain authoritative. File count alone never proves implementation completeness.

# END MASTER PROMPT #1