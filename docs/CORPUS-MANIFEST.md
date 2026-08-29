# MORPHEUS CORPUS MANIFEST

## Purpose
This repository uses a compressed engineering-corpus strategy: dense normative specifications, implementation prompts, schemas, code and small fixtures instead of literal duplicated prose. The goal is functional coverage of a very large project bible while keeping Git lightweight, auditable and maintainable.

## Canonical layers
1. `prompts/01-root.md` through `prompts/39-grand-master-final.md`: the **39-prompt canonical Engineering Bible**.
2. `prompts/30-grand-master.md`: historical Integration Checkpoint I, retained for continuity; not the final directive.
3. `prompts/39-grand-master-final.md`: true final integration/implementation directive.
4. `prompt-corpus/00-OMEGA-MASTER-PROMPT.md`: compressed integrated execution contract; useful context but subordinate to tested code/normative schemas and current canonical prompt #39 where prose conflicts.
5. `docs/`: implementation architecture, evidence, research, operations and product documents.
6. `backend/`, `core/`, `frontend/`: executable system and implementation authority together with normative schemas/tests.
7. `examples/`: small canonical workloads.
8. `PHASE_STATUS.md`, `ROADMAP.md`, `CHANGELOG.md`, `progress.json`: durable continuation/exact-head state.

## Coverage matrix
| Area | Canonical source | Implementation target |
|---|---|---|
| Vision/problem/theory | prompts 01–05 | README/docs + formal contracts |
| MWS/IR | prompts 06–07 | backend models/parser/WorkloadIR |
| Primitive ecosystem | prompts 08, 34 | core + backend catalog/manifest |
| Cost model/calibration | prompts 09, 33 | backend cost/calibration + benchmark |
| Search/Pareto | prompts 10, 37 | backend engine/search-quality |
| Code generation | prompt 11 | backend codegen + core/generated artifacts |
| Runtime adaptation | prompt 12 | backend runtime/migration/data-plane |
| Control plane | prompt 13 | FastAPI/backend/storage |
| UI/terminal | prompt 14 | React frontend |
| AI/copilot | prompt 15 | bounded evidence-grounded assistant |
| Benchmarks | prompt 16 | benchmark harness/research suite |
| Research | prompts 17, 37 | experiments/evaluation/docs |
| Paper/patent | prompt 18 | paper/prior-art/IP package |
| Production | prompt 19 | deployment/observability/worker controls |
| Testing/CI | prompts 20, 38 | tests + GitHub Actions |
| Product/startup | prompt 21 | product/pilot docs |
| Documentation | prompt 22 | docs/tutorials/contracts |
| Demo | prompt 23 | demo fixtures/flows |
| Ecosystem | prompts 24, 34 | primitive/plugin architecture |
| Roadmap | prompt 25 | ROADMAP.md |
| Reference architecture | prompt 26 | whole-system contracts/dataflow |
| AI build protocol | prompt 27 | durable execution loop |
| Audit | prompt 28 | FINAL-CHECKLIST.md + completion ledger |
| Release | prompt 29 | claim/release evidence tooling |
| First integration checkpoint | prompt 30 | historical integrated directive |
| Security/sandbox/privacy | prompt 31 | security/worker/evidence gates |
| Portability/ABI/FFI | prompt 32 | cross-platform CI/toolchain contracts |
| Hardware-aware systems | prompt 33 | MachineProfile/calibration/research |
| Advanced primitives | prompt 34 | future/implemented primitive lifecycle |
| Composite synthesis | prompt 35 | ConfigurationIR/ownership/routing/update semantics |
| Distributed/edge | prompt 36 | future/research frontier only unless implemented |
| Mathematics/algorithms | prompt 37 | equations/pseudocode/evaluation definitions |
| Contracts/tests/continuity | prompt 38 | API/schema/test/ADR/progress governance |
| Final integration | prompt 39 | canonical final implementation/completion directive |

## Compression rules
- Prefer contracts, tables, state machines, algorithms, schemas and acceptance criteria over repetitive narrative.
- Maintain one canonical definition per concept where practical.
- Large datasets, binaries, screenshots and benchmark dumps stay outside Git; preserve compact checksums/manifests instead.
- A prompt volume may reference another canonical volume rather than restating it.
- Every addition must make clear whether it is normative, explanatory, experimental, future/research or implemented.

## Truth-state vocabulary
Use these states deliberately in progress/evidence documents:
- `PROPOSED`: described only.
- `SCAFFOLDED`: file/API exists but behavior is incomplete.
- `IMPLEMENTED`: behavior exists in source.
- `TESTED`: automated test exists and has passed in a known environment.
- `MEASURED`: quantitative result was actually produced under a documented protocol.
- `VALIDATED`: repeated/independent evidence supports the scoped claim.
- `RESEARCH`: implemented or analyzed experimentally but not authorized as stable automatic behavior.
- `BLOCKED`: cannot safely/credibly proceed because a required condition/evidence is absent.

Measured/predicted/inferred/proposed labels must not be collapsed into each other.

## Corpus-integrity rule
The canonical `prompts/` directory contains exactly the 39 enumerated prompt filenames in `MASTER-INDEX.md`. Repository tests should verify:
- all 39 exist;
- #39 carries the canonical-final marker;
- #30 identifies itself as a checkpoint rather than the final Bible;
- README and AI-START-HERE point readers to #39;
- FINAL-CHECKLIST requires all 39 canonical prompt files.

## Repository completion rule
File count is not software completion. Prompt-corpus completeness and repository engineering-gate completeness are distinct evidence surfaces. A repository may report 100% only for an explicitly enumerated set of engineering gates that actually pass on the exact revision. Publication acceptance, patent/legal outcomes, independent benchmark validation, customer/production deployment, universal SOTA superiority and external certifications remain separate events.