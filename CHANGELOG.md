# CHANGELOG

All notable repository changes are recorded here. Truth-state labels follow `docs/CORPUS-MANIFEST.md`.

## 2026-08-28 — Adaptive bitmap benchmarking checkpoint

### Core / C++20
- Added adaptive sparse-array/dense-bitset containers for the partitioned `CompressedBitmap` primitive with promotion/demotion hysteresis.
- Added dense/dense bitwise union and intersection paths plus sparse/dense correctness coverage.
- Added `core/src/compressed_bitmap_bench.cpp`, a deterministic microbenchmark for intersection, union, membership and materialization across controlled cardinalities.
- Wired the adaptive bitmap benchmark into CMake and CTest with a smoke invocation so cross-platform CI verifies that the benchmark harness builds and executes.
- Added machine-readable CSV benchmark output plus `scripts/sweep_bitmap_benchmark.py` for deterministic cardinality/seed sweeps.
- Hardened the benchmark CLI and sweep parser so malformed arguments, seed overflow, missing executables, schema drift, missing operations, metadata mismatches and invalid negative measurements fail explicitly.
- Added an Ubuntu CI end-to-end sweep smoke over the sparse/dense boundary (`2048,4095,4096,4097,8192`) with deterministic seeds and artifact-shape validation.
- Added `scripts/analyze_bitmap_sweep.py` for deterministic median/min/max aggregation over repeated seeds.
- Hardened sweep analysis so non-finite timing data, unknown operations, malformed numeric fields, incomplete operation topology and inconsistent sample counts fail explicitly before threshold evidence is accepted.
- Added `--expect-samples` and wired the CI analyzer to require exactly two samples for every cardinality/operation pair in the smoke sweep.
- Strengthened analysis provenance by rejecting duplicate seeds, negative seeds, per-operation seed-set drift and inconsistent repetition metadata, preventing accidental pseudo-replication from being accepted as independent benchmark evidence.

### CI evidence
- GitHub Actions run `33125564450` completed successfully for adaptive bitmap transition tests at commit `48da2e5fc4c3f634d86a8ad789172f0371ed1852`.
- GitHub Actions run `33128997917` completed successfully for the benchmark/CMake checkpoint at commit `2257499d1a3b51dcd71fc09a17198b0fcc408215`.
- GitHub Actions run `33135250180` completed successfully for the hardened sweep-validation checkpoint at commit `330df1d76d9588451e716bed1ea638c27af74eeb`.
- GitHub Actions run `33138171452` completed successfully for the end-to-end threshold-sweep gate at commit `e5c47c4373fd99801e0548328529420620ac82db`.
- GitHub Actions run `33141297512` completed successfully for the sweep-analysis CI checkpoint at commit `3c22e030f2fb2c706b700395ebcd3f2087c2bbae`.
- The newer strict analyzer/sample/seed-topology commits require their own successful workflow completion before being called green.

### Truth boundaries retained
- The bitmap implementation is Roaring-inspired, not wire-compatible/full Roaring: run containers, SIMD specialization and serialized compatibility remain open.
- Current 4,096/2,048 promotion/demotion thresholds are engineering defaults until controlled benchmark sweeps justify measured tuning.
- CI benchmark smoke execution is a portability/build/data-contract gate, not publication-grade performance evidence.
- The analyzer summarizes and validates measurements; it does not automatically modify production thresholds.

### Next
- Close CI evidence for strict analyzer/sample/seed-topology validation.
- Sweep adaptive bitmap cardinalities on declared hardware and preserve raw results.
- Tune promotion/demotion thresholds from measured crossovers.
- Add run-container specialization only if measurements demonstrate a useful regime.
- Continue the remaining P2/P3 closure items before shifting core priority to Butterfly Engine.

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
