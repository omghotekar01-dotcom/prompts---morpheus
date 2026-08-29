# MORPHEUS

MORPHEUS is a workload-aware data-structure synthesis and engineering-intelligence platform. It accepts a declarative workload specification, searches feasible physical data-structure compositions, generates C++20 artifacts, preserves experiment provenance, verifies generated code against explicit gates, and exposes the process through a React/FastAPI Command Center.

This repository contains both the implementation and the **39-prompt MORPHEUS Engineering Bible**. Prompt #39 is the canonical final integration directive; prompt #30 is retained as the first integration checkpoint.

## Current implementation state

The current engineering vertical slice covers:

- typed MORPHEUS Workload Specification (MWS), safe YAML parsing and semantic hashing;
- deterministic typed WorkloadIR with explicit access-distribution semantics;
- capability-aware primitive selection and canonical ConfigurationIR;
- deterministic exhaustive search, greedy baseline, beam search, automatic strategy selection and Pareto-front extraction;
- hard feasibility gates that do not silently relax constraints;
- bootstrap and calibration-anchored cost modeling with explicit prediction provenance/uncertainty;
- implementation-, operation-, scale- and distribution-bound calibration identity;
- workload-aware calibration coverage that distinguishes exact matches, distribution mismatch, scale mismatch, stale implementation and missing evidence;
- distribution-aware mutation-maintenance cost with exact operation/distribution identity;
- C++20 primitive library including Robin Hood hash, a real B+ tree, sorted array, trie, adaptive bitmap baseline and CSR graph;
- standalone generated C++20 artifacts;
- cross-platform local compile verification;
- schema-derived stateful differential generated-artifact testing;
- C++20 ASan/UBSan CI gates;
- repeated calibration harnesses plus uniform/sequential/hotspot/Zipf distribution-calibration matrices;
- paired MORPHEUS-vs-C++-standard-library baseline matrix runner with frozen experiment manifests and paired statistics;
- optional specialist-container comparison adapters/smokes where available;
- SQLite workload/run/audit persistence and durable calibration profiles;
- content-addressed local artifact storage and SHA-256 evidence ledger;
- runtime drift, hysteresis, migration, rollback and local in-process versioned artifact routing;
- bounded no-shell local job worker with allowlisted executables, timeouts, cancellation and temporary workspaces;
- deterministic evidence-grounded Copilot plus an optional tool-restricted language translation boundary;
- feature-policy registry with stable/guarded/research/blocked states and fail-closed automatic-control policy;
- deterministic API-route contract and feature-policy fingerprints;
- frozen research experiment matrices, held-out prediction/ranking/regret evaluation and paired statistical analysis;
- artifact-backed claim gates, structural evidence validation and deterministic evidence-package tooling;
- strict reproducibility v2 manifest binding exact source commit, evidence bytes, API-contract fingerprint and feature-policy fingerprint;
- modern React/TypeScript Command Center with large readable typography and a light professional theme.

The canonical machine-readable engineering-completion surface is `GET /api/v2/completion`. It counts **explicit repository engineering gates only**. Publication acceptance, patent/legal outcomes, independent benchmark validation, external customer/production deployment, security/regulatory certification and universal performance superiority are intentionally outside that percentage.

See `PHASE_STATUS.md` and `progress.json` for the latest exact-head verified checkpoint and truth-state boundaries.

## Quick start on Windows

### 1. Clone

```powershell
git clone https://github.com/omghotekar01-dotcom/prompts---morpheus.git
cd prompts---morpheus
```

### 2. One-command launcher

Double-click:

```text
START-MORPHEUS.bat
```

or run:

```powershell
powershell -ExecutionPolicy Bypass -File .\START-MORPHEUS.ps1
```

The launcher creates the backend virtual environment when needed, installs missing backend/frontend dependencies, then starts both services.

Open:

- Command Center: `http://localhost:5173`
- Control-plane API: `http://localhost:8000`
- FastAPI docs: `http://localhost:8000/docs`
- v2 engineering completion: `http://localhost:8000/api/v2/completion`

## Manual development startup

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m uvicorn app.server:app --reload --port 8000
```

`app.server:app` preserves the mature v1 routes and mounts the evidence-safe v2 surfaces. The dependency pins include Python 3.14-compatible Windows wheels for the native dependencies used by the current project.

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

### C++20 core

```powershell
cmake -S core -B build/core -DCMAKE_BUILD_TYPE=Release
cmake --build build/core --config Release
ctest --test-dir build/core -C Release --output-on-failure
```

Optional sanitizer verification on GCC/Clang:

```bash
cmake -S core -B build/core-sanitized -DCMAKE_BUILD_TYPE=Debug -DMORPHEUS_ENABLE_SANITIZERS=ON
cmake --build build/core-sanitized
ctest --test-dir build/core-sanitized --output-on-failure
```

## Paired baseline evidence

After building the C++ core, run a controlled local standard-library comparison:

```bash
python3 benchmark/run_baseline_matrix.py \
  build/core/morpheus_baseline_bench \
  --sizes 1000 10000 100000 \
  --seeds 1337 2027 4242 \
  --ops 20000 \
  --repetitions 7 \
  --warmup 1 \
  --output-dir results/baseline
```

The runner writes a frozen experiment manifest, machine profile, baseline manifest, raw measurements, paired statistical summary and evidence index. These are local paired measurements. They are **not** automatically state-of-the-art or universal-speedup evidence.

## Distribution-bound calibration

For access-locality-sensitive evidence, use the dedicated distribution-calibration runner after building `morpheus_distribution_calibrate`:

```bash
python3 benchmark/run_distribution_calibration_matrix.py \
  build/core/morpheus_distribution_calibrate \
  --sizes 1000 10000 \
  --seeds 1337 2027 9001 \
  --distributions uniform sequential hotspot zipf \
  --ops 10000 \
  --repetitions 5 \
  --warmup 1 \
  --output-dir results/distribution-calibration
```

Each usable measurement is bound to exact physical implementation, operation, record-count scale and typed distribution parameters. A mismatch remains a mismatch rather than being silently extrapolated as exact evidence.

## Evidence-gated release package

A release package can include real evidence while failing closed on absent, invalid or semantically inconsistent artifacts. A descriptor supplies the exact source commit, requested claims and local evidence files with their declared SHA-256 values:

```bash
python -m release.evidence_package release-descriptor.json \
  --output-dir dist/morpheus-evidence \
  --zip dist/morpheus-evidence.zip
```

The packager verifies byte hashes, validates known evidence structures, checks locally decidable cross-artifact links, builds the release manifest from artifact roles that actually exist, and emits a deterministic ZIP. Merely writing an evidence-role name in a claim cannot authorize that claim.

## Repository map

```text
backend/
  app/                 parser, synthesis, cost/calibration, storage, runtime,
                       data-plane routing, verification, Copilot, policy/release gates
  tests/               Python, API, compile, differential, evidence and control tests

core/
  include/morpheus/    C++20 primitive/migration library
  src/                 demo, calibration and benchmark harnesses
  tests/               primitive/concurrency/migration tests

frontend/
  src/                 React/TypeScript Command Center

benchmark/             benchmark protocols, matrix runners and analysis assets
research/              frozen experiment protocol, workloads and research ledgers
release/               artifact-backed release/evidence packaging

docs/                  implementation, upgrade, research, paper, IP and pilot docs
examples/              compact MWS workload fixtures
prompt-corpus/         compressed Omega execution contract
prompts/               canonical 39-prompt MORPHEUS Engineering Bible
```

## End-to-end MORPHEUS flow

```text
MWS YAML/JSON
  -> safe validation + explicit resolution
  -> canonical WorkloadIR hash
  -> capability filtering
  -> exact calibration coverage + calibrated/bootstrap cost provenance
  -> exhaustive / greedy / beam search
  -> hard feasibility gates + Pareto candidates
  -> canonical physical ConfigurationIR
  -> generated C++20
  -> compile + stateful differential verification
  -> controlled benchmark/evidence
  -> content-addressed persistence + reproducibility manifest
  -> evidence-grounded explanation
  -> runtime drift/adaptation recommendation
  -> gated migration
  -> optional local in-process version activation / rollback
  -> claim-gated release evidence package
```

## Evidence classes

MORPHEUS deliberately keeps these concepts separate:

- **prediction** — model/prior output;
- **calibration measurement** — measured primitive operation under an exact machine/protocol/implementation/scale/distribution identity;
- **artifact compile evidence** — generated code accepted by a specific local toolchain;
- **correctness evidence** — generated behavior compared with a reference model on declared routes/sequences;
- **benchmark measurement** — measured behavior under a frozen workload/machine protocol;
- **runtime recommendation** — adaptation proposal derived from drift/benefit/switching-cost logic;
- **migration authorization** — verified control-plane permission to transition;
- **local data-plane activation** — atomic in-process artifact-route reference change;
- **release claim evidence** — packaged byte-identical artifacts satisfying explicit claim-role/semantic gates;
- **reproducibility identity** — hashes that bind source/contracts/evidence bytes, not an external scientific attestation or cryptographic authorship signature.

A stronger label must never be inferred from a weaker one.

## Important current boundaries

- The ordered primitive is a real B+ tree, but deletion uses a correctness-first rebuild path rather than an optimized underflow redistribution/merge implementation.
- The bitmap implementation is an adaptive posting/dense correctness-oriented structure, not a full production Roaring library implementation.
- Generated mutation handling is correctness-first and is not yet a fully optimized incremental physical-maintenance planner for every composition.
- Compile/differential verification runs as bounded local host processes; it is **not** a hardened container/VM/seccomp sandbox.
- Local data-plane activation provides versioned in-process reference switching and rollback. It does not establish native cross-process hot swap or arbitrary concurrent generated-object state transformation.
- SQLite + local content-addressed filesystem storage is a strong local prototype/control plane, not an HA multi-tenant production service.
- The optional language-provider contract may translate/classify wording only. Deterministic persisted evidence remains authoritative; no LLM can manufacture benchmark truth or feature maturity.
- Standard-library and optional specialist baselines do not automatically equal the strongest possible database/system comparison for every research claim.
- Broad automatic data-structure synthesis, physical-design tuning, adaptive indexing and workload-aware adaptation have substantial prior art. Novelty claims must be scoped to mechanisms actually demonstrated by MORPHEUS experiments.
- Distributed, edge/embedded and native cross-process replacement are future/research scopes unless explicitly implemented and promoted by the feature/capability registry.

## CI

GitHub Actions validates:

- backend tests on Python 3.11 and Python 3.14 on Ubuntu;
- backend tests on Windows Python 3.14 with native MSVC available;
- React/TypeScript production build;
- C++20 build/CTest on Ubuntu and Windows/MSVC;
- C++20 AddressSanitizer + UndefinedBehaviorSanitizer profile;
- calibration-matrix and distribution-calibration-matrix smokes;
- paired standard-library and optional specialist baseline smokes;
- primitive crossover/ordered-tree experiments used as protocol guards;
- native version-switch/cross-type migration publication smokes.

See `PHASE_STATUS.md` and `progress.json` for the latest verified exact-head checkpoint rather than assuming the newest commit is green.

## Engineering Bible

For an AI or engineer performing deep MORPHEUS work, read:

1. `PHASE_STATUS.md`
2. `progress.json`
3. `AI-START-HERE.md`
4. `prompts/39-grand-master-final.md` — canonical final directive
5. `prompts/25-v23-roadmap.md`
6. `prompts/26-v24-reference-architecture.md`
7. `prompts/27-v25-ai-build-protocol.md`
8. specialized prompts for the active phase (including #31–#38 advanced domains)
9. `prompts/28-v26-audit.md` and `FINAL-CHECKLIST.md` before completion/public claims

`prompts/30-grand-master.md` is a historical integration checkpoint, not the final Bible.

## Storage policy

Keep Git lightweight. Do not commit generated binaries, dependency directories, large raw benchmark datasets, large traces, model checkpoints or duplicate media. Preserve large reproducible artifacts outside Git and reference them by checksum/provenance where appropriate.

## Current research direction

The strongest MORPHEUS thesis is not a generic claim that automatic data-structure design exists for the first time. The research program focuses on a tighter integration of typed workload intent, heterogeneous/composite physical design, machine/distribution-bound calibration, constrained search, executable C++ artifacts, explicit correctness/evidence gates, uncertainty-aware evaluation, provenance and transition-cost-aware reversible adaptation.

See `docs/RESEARCH-RADAR.md`, `research/EXPERIMENT-PROTOCOL.md`, `benchmark/PROTOCOL.md`, `docs/UPGRADE-AND-COMPATIBILITY.md` and `release/README.md` for the research/release discipline.