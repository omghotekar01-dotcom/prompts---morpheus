# MORPHEUS CORPUS MANIFEST

## Purpose
This repository uses a compressed engineering-corpus strategy: dense normative specifications, implementation prompts, schemas, code and small fixtures instead of literal duplicated prose. The intent is to provide the functional coverage of a very large project bible while keeping Git lightweight and maintainable.

## Canonical layers
1. Existing `prompts/01-root.md` through `prompts/30-grand-master.md`: domain-specific Engineering Bible.
2. `prompt-corpus/00-OMEGA-MASTER-PROMPT.md`: integrated execution contract.
3. `docs/`: implementation architecture, evidence, research, operations and product documents.
4. `backend/`, `core/`, `frontend/`: executable system.
5. `examples/`: small canonical workloads.
6. `PHASE_STATUS.md`, `ROADMAP.md`, `CHANGELOG.md`, `progress.json`: durable continuation state.

## Coverage matrix
| Area | Canonical source | Implementation target |
|---|---|---|
| Vision/problem | prompts 01–05 | README/docs |
| MWS/IR | prompts 06–07 | backend models/parser |
| Primitive ecosystem | prompt 08 | core + backend catalog |
| Cost model | prompt 09 | backend engine/calibration |
| Search/Pareto | prompt 10 | backend engine |
| Code generation | prompt 11 | backend codegen + core templates |
| Runtime adaptation | prompt 12 | backend runtime + frontend timeline |
| Control plane | prompt 13 | FastAPI/backend |
| UI/terminal | prompt 14 | React frontend |
| AI/copilot | prompt 15 | bounded evidence-grounded assistant |
| Benchmarks | prompt 16 | benchmark harness |
| Research | prompt 17 | experiments/docs |
| Paper/patent | prompt 18 | research/IP package |
| Production | prompt 19 | deployment/observability |
| Testing/CI | prompt 20 | tests + GitHub Actions |
| Product/startup | prompt 21 | product docs |
| Documentation | prompt 22 | docs |
| Demo | prompt 23 | demo fixtures/script |
| Ecosystem | prompt 24 | primitive/plugin SDK |
| Roadmap | prompt 25 | ROADMAP.md |
| Architecture | prompt 26 | docs/reference architecture |
| AI build protocol | prompt 27 | progress loop |
| Audit | prompt 28 | FINAL-CHECKLIST.md |
| Release | prompt 29 | release manifest |
| Integration | prompt 30 + Omega | whole repository |

## Compression rules
- Prefer contracts, tables, state machines, algorithms, schemas and acceptance criteria over repetitive narrative.
- One canonical definition per concept.
- Large datasets, binaries, screenshots and benchmark dumps stay outside Git; store compact checksums/manifests instead.
- A prompt volume may reference another canonical volume rather than restating it.
- Every future addition must declare whether it is normative, explanatory, experimental or aspirational.

## Truth-state vocabulary
Use exactly these states in progress/evidence documents:
- `PROPOSED`: described only.
- `SCAFFOLDED`: file/API exists but behavior is incomplete.
- `IMPLEMENTED`: behavior exists in source.
- `TESTED`: automated test exists and has passed in a known environment.
- `MEASURED`: quantitative result was actually produced under a documented protocol.
- `VALIDATED`: independent/repeated evidence supports the claim.
- `BLOCKED`: cannot proceed because of an explicit external dependency.

## Repository completion rule
File count is not completion. The project is complete only to the highest truth state supported by reproducible evidence.