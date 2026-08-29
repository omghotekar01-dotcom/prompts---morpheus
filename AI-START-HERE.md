# AI START HERE — MORPHEUS

If you are the AI/engineering agent receiving this repository, do not read files randomly and do not infer completion from prompt prose.

## Reading order
1. `PHASE_STATUS.md` and `progress.json` — exact latest verified checkpoint and truth-state ledger.
2. `prompts/39-grand-master-final.md` — **canonical final mission, architecture and completion definition**.
3. `prompts/25-v23-roadmap.md` — execution order/milestones.
4. `prompts/26-v24-reference-architecture.md` — canonical contracts/dataflow.
5. `prompts/27-v25-ai-build-protocol.md` — autonomous execution discipline.
6. Read the specialized volume(s) for the active milestone. Advanced domains are prompts #31–#38.
7. Use `prompts/28-v26-audit.md` and `FINAL-CHECKLIST.md` before declaring anything complete.

`prompts/30-grand-master.md` is retained only as **Integration Checkpoint I** from the original 30-prompt corpus. It is not the final directive.

## Source priority
Tested code + normative schemas/contracts + current feature/capability registries > prompt #39/reference architecture > milestone prompt > specialized volume > historical checkpoint/prose. If documents conflict, do not silently average them; record the conflict and preserve the higher-authority/current contract.

## Execution rule
Inspect the exact repository head and existing tests first. Implement the smallest dependency-ready real vertical slice, add failure-catching tests, run focused/integration tests, push a coherent change, verify exact-head CI and continue. Do not stop at plans/placeholders when implementation is possible.

## Truth rule
Never invent benchmark results, customer traction, paper acceptance, patent status, novelty, completion percentage or support for features not implemented. Keep measured, predicted, inferred, proposed, research and blocked states separate.

A `100%` engineering percentage may mean only **100% of explicitly enumerated repository engineering gates**. It must not be converted into publication, patent, security-certification, independent-validation, production-deployment or universal-SOTA claims.

## Core proof path
`MWS -> validation/resolution -> WorkloadIR -> real primitives/compositions -> cost/calibration with provenance -> feasibility/search -> ConfigurationIR -> generated C++ -> compile -> differential correctness -> fair benchmark -> reproducibility/evidence manifest`.

If adaptation is claimed, additionally verify immutable observed snapshots, drift, transition-cost-aware decision, feature-policy authority, verified migration, safe retain/switch/rollback and cumulative-benefit evidence.

UI/AI/cloud layers must not substitute for the core proof path.

## Repository size rule
Do not add large generated artifacts to Git. Prefer source, Markdown, schemas, tests, small fixtures and manifests; keep heavy benchmark traces/results/binaries externally reproducible by hashes/references.

## Canonical corpus invariant
The Engineering Bible is exactly 39 canonical prompt files under `prompts/`, ending at `prompts/39-grand-master-final.md`. CI should fail if the corpus/index/entry-point references regress.