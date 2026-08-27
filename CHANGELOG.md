# CHANGELOG

All notable repository changes are recorded here. Truth-state labels follow `docs/CORPUS-MANIFEST.md`.

## 2026-08-27 — MORPHEUS vertical slice expands through P10

### Backend / Python
- Added typed MWS workload models, safe YAML parsing, semantic hashing and deterministic synthesis APIs.
- Added exhaustive, beam and automatic search strategy selection with hard feasibility gates and Pareto-front extraction.
- Added calibrated cost-model anchoring with explicit bootstrap-vs-calibrated provenance and uncertainty ratios.
- Added SQLite persistence for workloads, synthesis runs and audit events.
- Added content-addressed local artifact storage.
- Added generated C++20 artifact verification using a fixed non-shell compiler argument vector.
- Added deterministic evidence-grounded Copilot explanations over persisted synthesis runs.
- Added two-phase runtime adaptation control logic with drift detection, transition-cost gating, cooldown/hysteresis, pending confirmation and abort.
- Updated dependency pins to versions with Python 3.14 Windows wheels (`FastAPI 0.140.11`, `Pydantic 2.13.1`, `PyYAML 6.0.3`).
- Fixed Windows/MSYS2 verification so compiler temp files use a verifier-owned writable directory instead of falling back to `C:\\WINDOWS`.
- Added P10 held-out prediction evaluation primitives: MAE, RMSE, MAPE, signed bias, Spearman rho, Kendall tau-b, top-1 regret and worst absolute error.

### Core / C++20
- Added Robin Hood hash, ordered-tree proxy, sorted-array index, prefix trie and bitmap correctness baseline.
- Added C++20 unit tests and CMake/CTest integration.
- Added repeated calibration harness protocol v2 with build/query/update measurements, seed/repetition/warmup control, sample statistics, compiler provenance and checksum.

### Frontend / React
- Rebuilt the MORPHEUS Command Center into a spacious professional light theme.
- Increased typography throughout the entire interface: navigation, headings, cards, tables, code editor, metrics, status surfaces and controls.
- Added live backend version, calibration state, persistent state counts and capability matrix.
- Added search strategy selector, theoretical/evaluated configuration counts and Pareto explorer.
- Added prediction-source and uncertainty visibility.
- Added C++ compile-verification action and result surface.
- Added evidence-Copilot question/answer panel connected to persisted run evidence.
- Added recent experiment history and control-plane audit events.
- Preserved explicit evidence boundaries rather than displaying fabricated telemetry.

### CI evidence
- GitHub Actions run `33101236270` passed backend, frontend production build and C++20 core tests at commit `3ee6cbd70efd8244e5e4d098193f9ff7d9a14860`.
- P10 evaluator commits after that checkpoint require their own latest CI confirmation before being called green.

### Truth boundaries retained
- Compile success is not logical correctness or performance proof.
- Local calibration is not automatically publication-grade evidence.
- Runtime adaptation remains control-plane state logic; real process-level hot swap is not implemented.
- SQLite/local filesystem persistence is an MVP, not HA infrastructure.
- The evidence Copilot is deterministic; LLM authority is intentionally not implemented.

### Next
- Differential/stateful generated-artifact correctness testing.
- Sanitizer/property/fuzz gates.
- Reproducible benchmark orchestration and held-out validation.
- Beam-vs-exhaustive regret studies and specialist baselines.
- Runtime migration/shadow-build/atomic-swap path.
- P11 release/paper/patent/startup evidence package.

## 2026-08-27 — Implementation program begins
### Added
- `prompt-corpus/00-OMEGA-MASTER-PROMPT.md`: integrated build/research/product execution contract.
- `docs/CORPUS-MANIFEST.md`: canonical corpus map, compression policy and truth-state vocabulary.
- `PHASE_STATUS.md`: durable phase ledger.
- `ROADMAP.md`: dependency-driven implementation roadmap P0–P11.
- `progress.json`: machine-readable continuation state.

### Existing foundation retained
- 30-volume Engineering Bible under `prompts/`.
- `AI-START-HERE.md`, `MASTER-INDEX.md`, `FINAL-CHECKLIST.md`, `README.md`.

## 2026-08-25 — Engineering Bible established
- Existing 30 prompt volumes, index, AI start guide and final checklist committed.
