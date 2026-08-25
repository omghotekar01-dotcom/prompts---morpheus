# MASTER PROMPT #25 — V23: IMPLEMENTATION ROADMAP, MILESTONES & EXECUTION SYSTEM

Turn the MORPHEUS architecture into an executable engineering program. Optimize sequence for proof, dependency reduction and falsifiability—not visual impressiveness.

## Principle
Every milestone ends in a runnable vertical slice with acceptance tests. Never build UI, AI or cloud layers ahead of the deterministic synthesis core they expose.

## M0 Repository foundation
Monorepo boundaries, build tooling, formatting/type/lint, CI, version metadata, ADRs. Acceptance: clean clone builds/tests from documented command.

## M1 Specification
Implement MWS Alpha parser/schema/semantic validator/resolver/hash and WorkloadIR lowering. Acceptance: golden valid/invalid corpus and deterministic IR.

## M2 Primitive core
Implement initial primitives (strong hash, ordered tree/sorted representation; then bitmap/trie where semantics justify), capability manifests, reference adapters and differential tests. Acceptance: operations correct under randomized mutation sequences.

## M3 Cost/calibration
Microbenchmark harness, machine profile, empirical measurements, first transparent model and uncertainty/extrapolation flags. Acceptance: held-out prediction/ranking report.

## M4 Search
ConfigurationIR, feasibility, exhaustive tiny-space enumerator, greedy/beam search, Pareto support. Acceptance: heuristic compared against exhaustive empirical optimum on small spaces.

## M5 Code generation
Generate standalone C++20 artifact, build manifest, reference tests and sandbox compilation. Acceptance: generated candidate compiles and passes differential suite.

## M6 End-to-end CLI
`validate -> synthesize -> inspect -> benchmark -> export`. Acceptance: one canonical workload produces reproducible verified artifact from clean environment.

## M7 Composite structures
Multiple secondary structures, operation routing and update propagation. Acceptance: mixed workload demonstrates valid composite and measured comparison to best single primitive.

## M8 Runtime adaptation
Telemetry snapshots, drift metric, hysteresis, re-synthesis, rebuild/migration prototype. Acceptance: controlled phase-change experiment reports total benefit including switch cost.

## M9 Control plane/UI
Job service, persistence, workers, research terminal. Acceptance: web-triggered synthesis produces same semantic result as CLI for pinned inputs.

## M10 AI copilot
NL->MWS drafts, assumption ledger and evidence-grounded explanation. Acceptance: eval set proves no invalid spec reaches optimizer and measured/predicted claims stay separated.

## M11 Research package
Baselines, ablations, workload matrix, reproducible figures, prior-art matrix and artifact bundle. Acceptance: core claims regenerate from scripts/raw results.

## M12 Pilot/product
Real integration, developer workflow and measured engineering/performance value. Acceptance criteria defined with pilot before execution.

## Work management
For every task record owner, dependency, artifact, acceptance test, risk and evidence link. Use issues/boards if useful but repository manifests remain canonical. Keep a decision log and weekly "what is actually working" report.

## Anti-patterns
No fake completion percentages; no paper before experiments; no patent claims before prior-art/counsel; no microservices without scaling need; no LLM in optimizer truth path; no benchmark result without manifest; no new primitive without correctness tests.

## Deliverable
Create milestone files, dependency DAG, acceptance-test matrix, issue templates, definition-of-done, risk register and release checkpoints. The roadmap is successful only if another engineering team can execute it without relying on unstated chat context.
