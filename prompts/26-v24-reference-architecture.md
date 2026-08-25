# MASTER PROMPT #26 — V24: FINAL REFERENCE ARCHITECTURE & CONTRACT MAP

Define one canonical MORPHEUS architecture against which implementation, paper, UI and deployment are audited.

## End-to-end dataflow
`User/NL/Form/YAML -> MWS parser -> schema+semantic validation -> resolver -> WorkloadIR -> capability analysis -> candidate generator -> feasibility/pruning -> cost model -> search/Pareto -> finalist measurement -> ConfigurationIR -> codegen -> sandbox build -> differential correctness -> benchmark -> Artifact+Manifest -> runtime telemetry -> ObservedWorkloadSnapshot -> drift/adaptation -> optional re-synthesis`.

## Truth hierarchy
1 logical semantics/reference oracle; 2 measured benchmark records; 3 calibrated model predictions; 4 heuristics; 5 AI explanation. Lower levels may never overwrite higher-level evidence.

## Core contracts
MWS: external workload intent. WorkloadIR: normalized logical problem. PrimitiveManifest: capabilities/parameters. MachineProfile: calibrated environment. ConfigurationIR: selected physical composition/routing. CostEstimate: predicted metric+uncertainty+model ID. Measurement: empirical metric+protocol. ArtifactManifest: generated build provenance. ObservedWorkloadSnapshot: runtime facts. AdaptationDecision: evidence/policy/action.

## Module boundaries
`spec`, `ir`, `primitives`, `cost`, `search`, `codegen`, `verify`, `benchmark`, `runtime`, `controlplane`, `ui`, `ai`, `research`. Dependencies point toward stable domain contracts; UI/control-plane cannot leak into optimizer core.

## Ownership
A composite configuration explicitly owns primary record storage and secondary structures. Mutations are atomic at logical level: validate -> mutate primary -> update affected secondaries or rollback/fail according to implementation contract. Routing maps each logical operation to a compatible structure and post-processing path.

## Feasibility
Candidate is feasible iff all required operations are supported, mutation semantics remain correct, hard resource constraints hold under the chosen estimator/verified measurement policy, and codegen backend supports the configuration. Infeasible candidates never enter winner ranking.

## Optimization
For feasible C and workload W/machine H, evaluate objective over operation-weighted predicted/measured costs. Preserve vector metrics before scalarization. Pareto mode operates on vectors. Search budget and seed are explicit.

## Verification
No generated artifact is RELEASED unless it compiles and passes generated differential correctness tests. Performance cannot compensate for correctness failure.

## Reproducibility key
Result identity pins semantic workload hash + registry versions + machine profile + cost-model version + search policy/seed + ConfigurationIR + codegen version + compiler/toolchain + benchmark protocol.

## Runtime
Adaptation uses observed snapshots and total expected gain net of build/migration/switch cost, guarded by hysteresis/cooldown/confidence. It never edits historical experiment truth.

## Security boundary
Parsing/uploads, AI, build execution and runtime telemetry are untrusted boundaries. Compiler/generated binary executes isolated from control plane.

## Deliverable
Produce architecture diagram, dependency graph, sequence diagrams, contract schemas, invariants, failure taxonomy and ADR references. Reject any implementation that introduces a second conflicting meaning for a core concept.
