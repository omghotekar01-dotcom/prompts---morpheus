# MORPHEUS FINAL CHECKLIST

Use this before calling the project, paper, demo, patent package or startup build "complete". Check only what is supported by real repository evidence.

## A. Specification & Formal Core
- [ ] MWS versioned schema exists.
- [ ] YAML/JSON parsing is safe and deterministic.
- [ ] Semantic validator checks names, types, references, weights/rates, units and contradictions.
- [ ] Raw and resolved MWS are distinct.
- [ ] Assumptions/defaults are visible and versioned.
- [ ] Semantic hash is deterministic.
- [ ] WorkloadIR lowers deterministically from resolved MWS.
- [ ] Formal objective/constraints match software semantics.

## B. Primitive System
- [ ] PrimitiveManifest/capability schema exists.
- [ ] Initial real primitives are implemented, not mocked.
- [ ] Point/range/filter/update capabilities are explicit.
- [ ] Parameter spaces are typed and bounded.
- [ ] Every primitive passes reference/differential correctness tests.
- [ ] Composite ownership/update propagation semantics are defined.

## C. Cost Model & Machine Calibration
- [ ] MachineProfile is versioned/hashed.
- [ ] Microbenchmark harness records raw measurements.
- [ ] Dataset/workload generators are deterministic by seed.
- [ ] Predicted values are typed separately from measured values.
- [ ] Cost model records model/training/calibration provenance.
- [ ] Held-out accuracy and ranking metrics are reported.
- [ ] Extrapolation/low-confidence regions are flagged.

## D. Search & Optimization
- [ ] ConfigurationIR is canonical/hashable.
- [ ] Feasibility is applied before ranking.
- [ ] Hard constraints are never silently relaxed.
- [ ] Exhaustive enumeration works on small spaces.
- [ ] Greedy/beam/random strategies are tested where claimed.
- [ ] Search regret/optimality gap is measured against exhaustive empirical oracle.
- [ ] Pareto mode preserves raw metric vectors.
- [ ] Search seed/budget/version are recorded.

## E. Code Generation & Correctness
- [ ] Selected ConfigurationIR generates standalone code.
- [ ] Generated C++20 compiles from a clean environment.
- [ ] Build happens in an isolated sandbox.
- [ ] Generated API semantics match WorkloadIR.
- [ ] Stateful differential tests compare candidate to reference oracle.
- [ ] Insert/delete/modify keep all secondary structures synchronized.
- [ ] Correctness failure invalidates candidate regardless of speed.
- [ ] Artifact manifest records source/config/toolchain hashes.

## F. Benchmarking
- [ ] Strong baselines use identical logical semantics.
- [ ] Compiler flags/toolchain are recorded.
- [ ] Warmup/repetitions/cache mode are documented.
- [ ] Dead-code elimination/timer overhead are controlled.
- [ ] Memory metric is precisely defined.
- [ ] Absolute metrics and effect sizes are reported.
- [ ] Raw results can regenerate tables/figures.
- [ ] No fake/demo-only numbers are presented as measurements.

## G. Runtime Adaptation
- [ ] ObservedWorkloadSnapshot is separate from declared MWS.
- [ ] Drift metric/windowing is defined.
- [ ] Re-synthesis evaluates candidate under observed workload.
- [ ] Switching cost includes rebuild/migration overhead.
- [ ] Hysteresis/cooldown prevents oscillation.
- [ ] Adaptation experiment measures cumulative benefit including switch cost.
- [ ] Rollback/correctness validation exists if live switching is claimed.

## H. Backend, Security & Operations
- [ ] Durable job state machine exists.
- [ ] DB entities preserve immutable provenance.
- [ ] Large artifacts are outside DB/Git and referenced by hash.
- [ ] Worker cancellation/retry/failure semantics are explicit.
- [ ] Compiler/generated binaries are isolated from API process.
- [ ] Authz/tenant isolation exists if multi-user.
- [ ] Path traversal/injection/resource-exhaustion defenses are tested.
- [ ] Logs redact secrets/sensitive trace data.
- [ ] Backup/restore is tested if production deployment is claimed.

## I. UI / Developer Experience
- [ ] NL, wizard and raw editor converge on the same MWS contract.
- [ ] Validation errors/assumptions are visible.
- [ ] UI clearly labels PREDICTED vs MEASURED.
- [ ] Search/candidate/Pareto state is inspectable.
- [ ] Generated configuration/source/provenance are inspectable.
- [ ] Failed/infeasible states are handled honestly.
- [ ] CLI can execute the complete core path without the UI.

## J. AI Copilot
- [ ] AI is optional to core synthesis.
- [ ] NL->MWS output is validated before use.
- [ ] High-impact assumptions require review.
- [ ] AI explanations are grounded in structured evidence.
- [ ] Prompt injection from repo/uploads is treated as untrusted data.
- [ ] AI cannot invent measurements, novelty, patent status or implementation state.

## K. Research Quality
- [ ] RQs/hypotheses are written before final experiments.
- [ ] Strong baselines and ablations exist.
- [ ] Small-space empirical optimum is used where tractable.
- [ ] Cost-model leakage is prevented.
- [ ] Confidence intervals/sample counts are reported.
- [ ] Negative results/limitations are retained.
- [ ] Threats to validity are documented.
- [ ] Every quantitative paper claim maps to experiment IDs/raw data.

## L. Prior Art, Paper & Patent
- [ ] Literature search covers mechanism families, not just "MORPHEUS".
- [ ] Patent search log exists.
- [ ] Novelty matrix distinguishes SAME/PARTIAL/DIFFERENT/UNKNOWN.
- [ ] "First/novel/state-of-the-art" claims are supported or removed.
- [ ] Patent filing status is stated accurately.
- [ ] Patent counsel reviews actual claims if filing is pursued.
- [ ] Paper distinguishes proposed, implemented and measured functionality.

## M. Product / Startup
- [ ] Initial user/persona hypothesis is validated through interviews/pilots.
- [ ] Product value is measured against current workaround.
- [ ] Local CLI/core works before SaaS complexity.
- [ ] Integration workflow is incremental/reversible.
- [ ] Pricing/market/customer claims are evidence-based.
- [ ] Generated-code licensing is clear.

## N. Documentation & Reproducibility
- [ ] README states only what is implemented.
- [ ] Quickstart works from clean clone.
- [ ] MWS/IR/API normative specifications match code.
- [ ] Canonical tutorial uses real outputs.
- [ ] Primitive-author guide exists if ecosystem is claimed.
- [ ] Research reproduction guide exists.
- [ ] Schema/examples/docs are tested in CI.
- [ ] Release manifest pins source/model/machine/toolchain/experiment versions.

## O. Demo / Competition
- [ ] Demo shows real problem -> synthesis -> correctness -> evidence.
- [ ] Baseline comparison is fair.
- [ ] Predicted vs measured values are visually distinct.
- [ ] Offline/failure-safe demo path exists.
- [ ] Judge Q&A explains novelty limits and current implementation honestly.
- [ ] Poster/deck uses reproducible figures, not invented metrics.

## P. Repository Hygiene
- [ ] All 30 prompt files exist and are indexed.
- [ ] README, AI-START-HERE, MASTER-INDEX and this checklist exist.
- [ ] No unnecessary large binaries/PDFs/images/traces are committed.
- [ ] One canonical file per concept; avoid `final-v2-final` duplicates.
- [ ] Heavy datasets/results are regenerated or externally referenced by checksum.
- [ ] Secrets are absent from Git history.

## Q. Final World-Class Gate
The project may be described as a complete MORPHEUS research prototype only if a clean environment can execute:

`MWS -> validate -> WorkloadIR -> real primitive candidates -> calibrated cost/search -> ConfigurationIR -> generated code -> compile -> differential correctness -> baseline benchmark -> reproducibility manifest`

and reproduce the evidence for the claims being shown.

If adaptation is claimed, additionally reproduce:

`runtime snapshots -> drift -> candidate re-evaluation -> transition-cost decision -> safe switch/retain -> cumulative benefit measurement`.

### Final truth test
Before any public claim, answer with evidence:
1. Why did MORPHEUS choose this design?
2. Is the generated design logically correct?
3. Is its performance advantage actually measured fairly?
4. Can another evaluator reproduce it?
5. What does MORPHEUS still NOT support?

If any answer is unclear, the relevant item remains incomplete.
