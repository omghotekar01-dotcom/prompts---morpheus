# MASTER PROMPT #30 — MORPHEUS INTEGRATION CHECKPOINT I

## Status
This file is retained as the first integrated MORPHEUS build directive from the original 30-prompt checkpoint. It is **not** the final Engineering Bible. Continue with prompts #31–#39. The canonical final integration directive is `prompts/39-grand-master-final.md`.

Tested code, normative schemas/contracts and the current feature/capability registry have higher authority than older prose when implementation has evolved.

## Mission checkpoint
Build a workload-aware physical data-structure synthesis system in which users describe dataset/schema, logical operations, frequencies/rates, distributions/selectivities, updates, constraints and objectives; MORPHEUS validates and normalizes that intent, explores compatible physical configurations, predicts and measures costs on the target machine, generates executable implementations, proves logical correctness against a reference model, and optionally adapts when observed workload changes.

MORPHEUS is not "AI chooses a data structure." The core is deterministic systems engineering: specification + IR + capability algebra + empirical cost modelling + constrained configuration search + code generation + verification + reproducible benchmarking. AI is an optional specification/explanation layer.

## Absolute invariants
1. Correctness before performance.
2. Measured != predicted != inferred.
3. Hard constraints are never silently relaxed.
4. Unsupported functionality is rejected, never simulated with fake output.
5. Workload intent is separate from physical design choice.
6. Every important result has provenance/version/hash.
7. Search quality is tested against exhaustive small spaces.
8. Generated code is untrusted until verification passes.
9. LLM output never overrides validator/optimizer/benchmark truth.
10. Scientific/product claims never exceed evidence.

## Checkpoint pipeline
`NL/Form/YAML -> MWS -> validation/resolution -> WorkloadIR -> primitive registry/capabilities -> candidate generation -> feasibility -> cost prediction+uncertainty -> search/Pareto -> ConfigurationIR -> codegen -> compile -> differential correctness -> benchmark -> artifact/manifest -> runtime telemetry -> guarded re-synthesis/migration`.

## Checkpoint build order
### A — Formal core
Versioned MWS, semantic validation, canonicalization, semantic hashing and deterministic WorkloadIR.

### B — Primitive laboratory
Trusted reference semantics and real physical primitives with capability manifests, parameters, memory/build/update hooks and differential/stateful tests.

### C — Empirical intelligence
Deterministic workload generators, benchmark harness, MachineProfile/calibration and transparent cost model with uncertainty.

### D — Synthesis
ConfigurationIR, ownership/routing, feasibility, exhaustive tiny-space oracle, greedy/beam search and Pareto exploration.

### E — Compiler output
Generate C++20, compile, differential-test against an independent logical oracle, then benchmark and preserve evidence.

### F — End-to-end developer product
Expose the real core through CLI/API and an inspectable UI. UI progress and telemetry must derive from actual state.

### G — Composition
Allow multiple physical structures only with explicit primary/secondary ownership, update propagation and memory accounting.

### H — Adaptation
Use immutable observed workload snapshots, drift, switching cost, hysteresis/cooldown, verified migration and rollback.

### I — AI assistance
NL->MWS and evidence-grounded explanation only. AI cannot create evidence or override deterministic decisions.

### J — Research/product hardening
Strong baselines, ablations, statistics, security, reproducibility, release artifacts, prior-art/IP discipline and pilot validation.

## Core contracts
Maintain versioned MWS, WorkloadIR, PrimitiveManifest, MachineProfile, CostEstimate, ConfigurationIR, Measurement, ExperimentManifest, ArtifactManifest, ObservedWorkloadSnapshot and AdaptationDecision contracts.

## Evidence rules
Predictions remain predictions. Primitive calibration is machine/protocol scoped. Candidate-level measurement is stronger only for the exact artifact/workload/machine. CI benchmark smokes are protocol checks, not publication-grade superiority evidence. Every quantitative public claim maps to frozen evidence.

## Runtime rule
Expected long-horizon benefit must exceed transition/switching cost under the declared safety policy before automatic change is even considered. Feature-policy authority, correctness validation and exact-generation rollback remain mandatory.

## Repository/storage rule
Keep Git compact: source, Markdown, schemas, tests, small fixtures and manifests. Keep large generated binaries, raw benchmark dumps, traces and model/data artifacts outside Git with hashes/references.

## Why prompts #31–#39 were added
The original checkpoint did not fully isolate advanced security/sandboxing, cross-platform ABI/FFI, hardware-aware optimization, the extended primitive universe, composite-routing semantics, distributed/edge frontiers, mathematical pseudocode, contract/test continuity and a final integrated completion definition. Those domains are now canonical dedicated volumes.

## Continue here
Read, in order when performing final integration:
1. `prompts/31-v28-security.md`
2. `prompts/32-v29-portability.md`
3. `prompts/33-v30-hardware.md`
4. `prompts/34-v31-advanced-primitives.md`
5. `prompts/35-v32-composite-synthesis.md`
6. `prompts/36-v33-distributed-edge.md`
7. `prompts/37-v34-math-algorithms.md`
8. `prompts/38-v35-contracts-tests-continuity.md`
9. `prompts/39-grand-master-final.md`

# INTEGRATION CHECKPOINT — CONTINUE WITH PROMPTS #31–#39