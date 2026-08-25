# AI START HERE — MORPHEUS

If you are the AI/engineering agent receiving this repository, do not read files randomly.

## Reading order
1. `prompts/30-grand-master.md` — integrated mission and invariants.
2. `prompts/25-v23-roadmap.md` — execution order/milestones.
3. `prompts/26-v24-reference-architecture.md` — canonical contracts/dataflow.
4. `prompts/27-v25-ai-build-protocol.md` — autonomous execution discipline.
5. Read the specialized volume(s) for the milestone being implemented.
6. Use `prompts/28-v26-audit.md` and `FINAL-CHECKLIST.md` before declaring anything complete.

## Source priority
Tested code + normative schemas/contracts > Grand Master/reference architecture > milestone prompt > specialized volume > older prose. If two documents conflict, do not silently average them; record the conflict and preserve the higher-authority/latest explicitly designated contract.

## Execution rule
Inspect repository and run existing tests first. Then implement the smallest dependency-ready vertical slice, test it, record evidence and continue. Do not stop at plans or placeholders when implementation is possible.

## Truth rule
Never invent benchmark results, customer traction, paper acceptance, patent status, novelty, completion percentage or support for features not implemented. Keep measured, predicted and inferred data separate.

## Core proof path
MWS -> validation -> WorkloadIR -> primitives -> cost/calibration -> search -> ConfigurationIR -> generated C++ -> compile -> differential correctness -> benchmark -> provenance manifest. UI/AI/cloud layers must not substitute for this path.

## Repository size rule
Do not add large generated artifacts to Git. Prefer code/spec/manifests and regenerate heavy outputs externally.
