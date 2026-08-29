# MORPHEUS FINAL CHECKLIST

Use this before calling the repository engineering prototype, paper evidence package, demo, patent package or startup build "complete". Check only what is supported by real repository evidence. This is an audit checklist, **not a statement that every aspirational/product/external item is already complete**.

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
- [ ] Every search-eligible primitive passes reference/differential correctness tests appropriate to its semantics.
- [ ] Composite ownership/update propagation semantics are defined for supported compositions.

## C. Cost Model & Machine Calibration
- [ ] MachineProfile is versioned/hashed.
- [ ] Microbenchmark harness records raw measurements.
- [ ] Dataset/workload generators are deterministic by seed.
- [ ] Predicted values are typed separately from measured values.
- [ ] Cost model records model/training/calibration provenance.
- [ ] Held-out accuracy and ranking metrics are reported where calibration quality is claimed.
- [ ] Extrapolation/low-confidence regions are flagged.
- [ ] Implementation/operation/scale/distribution mismatch fails closed for exact calibration lookup.

## D. Search & Optimization
- [ ] ConfigurationIR is canonical/hashable.
- [ ] Feasibility is applied before ranking.
- [ ] Hard constraints are never silently relaxed.
- [ ] Exhaustive enumeration works on small spaces.
- [ ] Greedy/beam strategies are tested where claimed.
- [ ] Search regret/optimality gap is measured against an explicitly named model/empirical oracle.
- [ ] Pareto mode preserves raw metric vectors.
- [ ] Search seed/budget/version are recorded where relevant.

## E. Code Generation & Correctness
- [ ] Selected ConfigurationIR generates standalone code.
- [ ] Generated C++20 compiles from a clean supported environment.
- [ ] Execution/build isolation level is accurately labeled; a hardened sandbox is claimed only if implemented.
- [ ] Generated API semantics match WorkloadIR/ConfigurationIR.
- [ ] Stateful differential tests compare candidate to an independent logical reference.
- [ ] Insert/delete/modify keep supported secondary structures synchronized.
- [ ] Correctness failure invalidates candidate regardless of speed.
- [ ] Artifact manifest records source/config/toolchain hashes.

## F. Benchmarking
- [ ] Strong baselines use identical logical semantics.
- [ ] Compiler flags/toolchain are recorded.
- [ ] Warmup/repetitions/cache mode are documented.
- [ ] Dead-code elimination/timer overhead are controlled where relevant.
- [ ] Memory metric is precisely defined.
- [ ] Absolute metrics and effect sizes are reported for public quantitative claims.
- [ ] Raw results can regenerate tables/figures used in claims.
- [ ] No fake/demo-only numbers are presented as measurements.
- [ ] CI smoke measurements are not represented as publication-grade superiority evidence.

## G. Runtime Adaptation
- [ ] ObservedWorkloadSnapshot is separate from declared MWS.
- [ ] Drift metric/windowing is defined.
- [ ] Re-synthesis evaluates candidate under observed workload semantics.
- [ ] Switching cost includes rebuild/migration overhead.
- [ ] Hysteresis/cooldown prevents oscillation where automatic switching is enabled.
- [ ] Adaptation experiment measures cumulative benefit including switch cost when adaptation benefit is claimed.
- [ ] Rollback/correctness validation exists for the exact switching mechanism claimed.
- [ ] Research-only classifiers cannot authorize automatic control without explicit feature-policy promotion.

## H. Backend, Security & Operations
- [ ] Durable job state machine exists for long-running work where claimed.
- [ ] DB entities preserve immutable provenance.
- [ ] Large artifacts are outside DB/Git and referenced by hash.
- [ ] Worker cancellation/retry/failure semantics are explicit.
- [ ] Compiler/generated binaries are outside the API process.
- [ ] Authz/tenant isolation exists before multi-user hosted claims.
- [ ] Path traversal/injection/resource-exhaustion defenses are tested.
- [ ] Logs redact secrets/sensitive trace data where applicable.
- [ ] Backup/restore is tested if production deployment is claimed.
- [ ] Sandbox/security maturity is described without upgrading bounded host-process execution into a stronger certification claim.

## I. UI / Developer Experience
- [ ] NL, wizard and raw editor converge on the same validated MWS contract where those interfaces exist.
- [ ] Validation errors/assumptions are visible.
- [ ] UI clearly labels PREDICTED vs MEASURED.
- [ ] Search/candidate/Pareto state is inspectable.
- [ ] Generated configuration/source/provenance are inspectable.
- [ ] Failed/infeasible states are handled honestly.
- [ ] Core workflow remains available without relying on visual presentation or an LLM.

## J. AI Copilot
- [ ] AI is optional to core synthesis.
- [ ] NL->MWS output is validated before use.
- [ ] High-impact assumptions require deterministic validation/review.
- [ ] AI explanations are grounded in structured evidence.
- [ ] Prompt injection from repo/uploads is treated as untrusted data.
- [ ] AI cannot invent measurements, novelty, patent status, feature maturity or implementation state.
- [ ] AI cannot authorize blocked/research automatic-control features through text alone.

## K. Research Quality
- [ ] RQs/hypotheses are written before final experiments.
- [ ] Strong baselines and ablations exist for claims being tested.
- [ ] Small-space empirical/model optimum is used where tractable and labeled correctly.
- [ ] Cost-model leakage is prevented.
- [ ] Confidence intervals/sample counts are reported where statistical claims are made.
- [ ] Negative results/limitations are retained.
- [ ] Threats to validity are documented.
- [ ] Every quantitative paper claim maps to experiment IDs/raw evidence.

## L. Prior Art, Paper & Patent
- [ ] Literature search covers mechanism families, not just "MORPHEUS".
- [ ] Patent search log exists before strong patentability claims.
- [ ] Novelty matrix distinguishes SAME/PARTIAL/DIFFERENT/UNKNOWN or equivalent evidence states.
- [ ] "First/novel/state-of-the-art" claims are supported for exact scope or removed.
- [ ] Patent filing status is stated accurately.
- [ ] Patent counsel reviews actual claims if filing is pursued.
- [ ] Paper distinguishes proposed, implemented and measured functionality.

## M. Product / Startup
- [ ] Initial user/persona hypothesis is validated through interviews/pilots before traction claims.
- [ ] Product value is measured against current workaround before ROI claims.
- [ ] Local core/SDK workflow works before unnecessary SaaS complexity.
- [ ] Integration workflow is incremental/reversible where possible.
- [ ] Pricing/market/customer claims are evidence-based.
- [ ] Generated-code/licensing implications are clear.

## N. Documentation & Reproducibility
- [ ] README states only what is implemented and preserves current limitations.
- [ ] Quickstart works from a clean supported environment.
- [ ] MWS/IR/API normative specifications match code.
- [ ] Canonical tutorial/demo uses real outputs.
- [ ] Primitive-author guide exists before claiming a mature external plugin ecosystem.
- [ ] Research reproduction guide exists for published/competition claims.
- [ ] Schema/examples/docs critical to execution are tested where practical.
- [ ] Release/reproducibility manifests pin source, contract, machine/toolchain and evidence identity appropriate to the claim.

## O. Demo / Competition
- [ ] Demo shows real problem -> synthesis -> correctness -> evidence.
- [ ] Baseline comparison is fair.
- [ ] Predicted vs measured values are visually distinct.
- [ ] Offline/failure-safe demo path exists where needed.
- [ ] Judge Q&A explains novelty limits and current implementation honestly.
- [ ] Poster/deck uses reproducible figures, not invented metrics.

## P. Repository & Corpus Hygiene
- [ ] All **39 canonical prompt files** exist under `prompts/` and are indexed in `MASTER-INDEX.md`.
- [ ] `prompts/39-grand-master-final.md` is the canonical final directive.
- [ ] `prompts/30-grand-master.md` is labeled as an integration checkpoint, not the final Bible.
- [ ] README and AI-START-HERE direct new agents to prompt #39.
- [ ] README, AI-START-HERE, MASTER-INDEX, CORPUS-MANIFEST and this checklist exist.
- [ ] Automated corpus-integrity tests fail if the canonical 39-prompt set or final-reference rules regress.
- [ ] No unnecessary large binaries/PDFs/images/traces are committed.
- [ ] One canonical file per concept; avoid `final-v2-final` duplicates.
- [ ] Heavy datasets/results are regenerated or externally referenced by checksum.
- [ ] Secrets are absent from repository content and release packages.

## Q. Final Repository Engineering Gate
The local research-engineering prototype may be described as repository-engineering complete only if a clean supported environment can execute the implemented proof path:

`MWS -> validate/resolve -> WorkloadIR -> real primitive/composite candidates -> calibration/provenance-aware cost/search -> ConfigurationIR -> generated code -> compile -> differential correctness -> fair benchmark/evidence -> reproducibility manifest`

and reproduce the evidence for the claims being shown.

If adaptation benefit or live switching is claimed, additionally reproduce the exact implemented scope:

`immutable observed snapshots -> drift -> candidate re-evaluation -> transition-cost decision -> feature-policy/safety gates -> verified migration -> safe switch/retain/rollback -> cumulative benefit measurement`.

### Final truth test
Before any public claim, answer with evidence:
1. Why did MORPHEUS choose this design?
2. Is the generated design logically correct under the declared semantics?
3. Which performance values are predicted and which are actually measured fairly?
4. Can another evaluator reproduce the scoped result?
5. What does MORPHEUS still NOT support?
6. Does the exact current head have green mandatory CI?
7. Does the claim gate authorize the exact wording from artifacts actually present?

If any relevant answer is unclear, that claim/gate remains incomplete.

## What a repository `100%` is allowed to mean
Only: **100% of explicitly enumerated repository engineering gates have passed on the stated exact revision.** It does not mean paper acceptance, patent filing/grant/freedom-to-operate, independent benchmark replication, real customer traction, external production deployment, universal state-of-the-art performance, security certification or regulatory approval.