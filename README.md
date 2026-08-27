# MORPHEUS

MORPHEUS is a workload-aware data-structure synthesis and engineering intelligence platform. It accepts a declarative workload specification, searches feasible physical data-structure compositions, generates C++20 artifacts, preserves experiment provenance, verifies generated code against explicit gates, and exposes the process through a React/FastAPI Command Center.

This repository contains both the implementation and the MORPHEUS Engineering Bible / master prompt corpus.

## Current implementation state

The current engineering vertical slice covers:

- typed MORPHEUS Workload Specification (MWS), safe YAML parsing and semantic hashing;
- capability-aware primitive selection;
- deterministic exhaustive search, beam search and automatic strategy selection;
- hard feasibility gates and Pareto-front extraction;
- bootstrap and calibration-anchored cost modeling with explicit prediction provenance;
- C++20 primitive library including Robin Hood hash, a real B+ tree, sorted array, trie and bitmap correctness baseline;
- standalone generated C++20 artifacts;
- cross-platform local compile verification;
- schema-derived stateful differential generated-artifact testing;
- C++20 ASan/UBSan CI gates;
- repeated calibration harness protocol v2;
- paired MORPHEUS-vs-C++-standard-library baseline matrix runner with frozen experiment manifests and paired statistics;
- SQLite workload/run/audit persistence and durable calibration profiles;
- content-addressed local artifact storage and SHA-256 evidence ledger;
- runtime drift, hysteresis, migration, rollback and local in-process versioned artifact routing;
- bounded no-shell local job worker with allowlisted executables, timeouts, cancellation and temporary workspaces;
- deterministic evidence-grounded Copilot plus an optional tool-restricted language translation boundary;
- P10 frozen experiment matrices, held-out prediction/ranking/regret evaluation and paired statistical analysis;
- P11 artifact-backed claim gates, structural evidence validation and deterministic evidence-package tooling;
- modern React/TypeScript Command Center with large readable typography and a light professional theme.

The canonical machine-readable engineering completion surface is `GET /api/v2/completion`. It counts repository engineering gates only; publication acceptance, patent/legal outcomes, independent validation, external customer deployment and universal performance superiority are intentionally outside that percentage.

See `PHASE_STATUS.md` for the broader truth-state ledger and boundaries.

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

The runner writes a frozen experiment manifest, machine profile, baseline manifest, raw measurements, paired statistical summary and evidence index. These are local paired measurements. They are **not** automatically a state-of-the-art or universal-speedup claim.

## Evidence-gated release package

P11 can package real evidence while failing closed on absent or structurally invalid artifacts. A descriptor supplies the exact source commit, requested claims and local evidence files with their declared SHA-256 values. Run:

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
                       data-plane routing, verification, Copilot, release gates
  tests/               Python, API, compile, differential and control-plane tests

core/
  include/morpheus/    C++20 primitive library
  src/                 demo, calibration and paired baseline harnesses
  tests/               primitive and structural tests

frontend/
  src/                 React/TypeScript Command Center

benchmark/             benchmark protocol, matrix runners and measurement assets
research/              frozen experiment protocol and research ledgers
release/               artifact-backed release/evidence packaging

docs/                  implementation, paper, prior-art and pilot documentation
examples/              MWS workload fixtures
prompt-corpus/         Omega integrated master prompt
prompts/               original 30-volume Engineering Bible
```

## End-to-end MORPHEUS flow

```text
MWS YAML
  -> safe validation
  -> canonical semantic hash
  -> capability filtering
  -> calibrated / bootstrap cost estimation
  -> exhaustive / beam search
  -> hard feasibility gates
  -> Pareto candidates
  -> selected physical plan
  -> generated C++20
  -> compile + differential verification
  -> content-addressed evidence
  -> persisted experiment record
  -> evidence-grounded explanation
  -> runtime drift/adaptation recommendation
  -> gated migration
  -> optional local in-process version activation / rollback
  -> claim-gated evidence package
```

## Evidence classes

MORPHEUS deliberately keeps these concepts separate:

- **prediction** — model output;
- **calibration measurement** — measured primitive operation under a machine/protocol;
- **artifact compile evidence** — generated code accepted by a specific local toolchain;
- **correctness evidence** — generated behavior compared with a reference model on declared routes/sequences;
- **benchmark measurement** — measured behavior under a frozen workload/machine protocol;
- **runtime recommendation** — adaptation proposal derived from drift/benefit/switching-cost logic;
- **migration authorization** — verified control-plane permission to transition;
- **local data-plane activation** — atomic in-process artifact-route reference change;
- **release claim evidence** — packaged byte-identical artifacts satisfying an explicit claim-role gate.

A stronger label must never be inferred from a weaker one.

## Important current boundaries

- The ordered primitive is now a real B+ tree, but deletion uses a correctness-first rebuild path rather than optimized underflow redistribution/merge.
- The bitmap primitive is a posting-vector correctness baseline rather than a compressed Roaring implementation.
- Generated mutation handling rebuilds selected indexes for correctness-first semantics and is not yet an optimized incremental update planner.
- Compile/differential verification runs as bounded local host processes; it is not a hardened container/VM/seccomp sandbox.
- Local data-plane activation provides versioned in-process reference switching and rollback. It does not establish native generated-object migration, cross-process hot swap or production concurrent record transformation.
- SQLite + local content-addressed filesystem storage is a strong local MVP, not an HA/multi-tenant production control plane.
- The optional language-provider contract can translate/classify wording only. Deterministic persisted evidence remains authoritative; no external LLM is permitted to manufacture benchmark truth.
- Standard-library paired baselines are not equivalent to contemporary specialist-library or database-system comparisons.
- Broad automatic data-structure synthesis, physical-design tuning, adaptive indexing and workload-aware adaptation have prior art. Novelty claims must be scoped to mechanisms actually demonstrated by MORPHEUS experiments.

## CI

GitHub Actions validates:

- backend tests on Python 3.11 and Python 3.14 on Ubuntu;
- backend tests on Windows Python 3.14 with native MSVC available;
- React/TypeScript production build;
- C++20 build/CTest on Ubuntu and Windows/MSVC;
- C++20 AddressSanitizer + UndefinedBehaviorSanitizer profile;
- calibration-matrix smoke;
- paired standard-library baseline-matrix smoke.

See `PHASE_STATUS.md` and `progress.json` for the latest verified checkpoint rather than assuming the newest commit is green.

## Engineering Bible

For an AI or engineer performing deep MORPHEUS work, read:

1. `PHASE_STATUS.md`
2. `progress.json`
3. `CHANGELOG.md`
4. `ROADMAP.md`
5. `AI-START-HERE.md`
6. `prompt-corpus/00-OMEGA-MASTER-PROMPT.md`
7. `prompts/30-grand-master.md`
8. specialized prompt volumes for the active phase
9. `FINAL-CHECKLIST.md` before completion claims

## Storage policy

Keep Git lightweight. Do not commit generated binaries, dependency directories, large raw benchmark datasets, large traces, model checkpoints or duplicate media. Preserve large reproducible artifacts outside Git and reference them by checksum/provenance where appropriate.

## Current research direction

The strongest MORPHEUS thesis is not a generic claim that automatic data-structure design exists for the first time. The research program focuses on the tighter integration of typed workload intent, capability algebra, calibrated compositional search, executable artifacts, explicit correctness/evidence gates, uncertainty-aware evaluation, provenance and transition-cost-aware resynthesis.

See `docs/RESEARCH-RADAR.md`, `research/EXPERIMENT-PROTOCOL.md`, `benchmark/PROTOCOL.md` and `release/README.md` for the research/release discipline.
