# MORPHEUS

MORPHEUS is a workload-aware data-structure synthesis and engineering intelligence platform. It accepts a declarative workload specification, searches feasible physical data-structure compositions, generates C++20 artifacts, preserves experiment provenance, verifies generated code against explicit gates, and exposes the process through a React/FastAPI Command Center.

This repository contains both the implementation and the MORPHEUS Engineering Bible / master prompt corpus.

## Current implementation state

The current tested vertical slice covers:

- typed MORPHEUS Workload Specification (MWS);
- safe YAML parsing and semantic hashing;
- capability-aware primitive selection;
- deterministic exhaustive search, beam search and automatic strategy selection;
- hard feasibility gates and Pareto-front extraction;
- bootstrap and calibration-anchored cost modeling with explicit prediction provenance;
- C++20 primitive library;
- standalone generated C++20 artifacts;
- local fixed-policy compile verification;
- stateful differential generated-artifact testing;
- repeated calibration harness protocol v2;
- SQLite workload/run/audit persistence;
- content-addressed local artifact storage;
- runtime drift + hysteresis control-plane logic;
- deterministic evidence-grounded Copilot;
- P10 held-out prediction/ranking/regret evaluation primitives;
- modern React/TypeScript Command Center with large readable typography and a light professional theme.

See `PHASE_STATUS.md` for the exact truth-state ledger and boundaries.

## Quick start on Windows

### 1. Clone

```powershell
git clone https://github.com/omghotekar01-dotcom/prompts---morpheus.git
cd prompts---morpheus
```

### 2. One-command launcher

After the first clone, double-click:

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

## Manual development startup

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

The current dependency pins include Python 3.14-compatible Windows wheels for the previously problematic native dependencies.

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

## Repository map

```text
backend/
  app/                 FastAPI control plane, parser, synthesis, cost model,
                       calibration, persistence, runtime, verification, Copilot
  tests/               Python, compile and stateful differential tests

core/
  include/morpheus/    C++20 primitive library
  src/                 demo + calibration harness
  tests/               primitive tests

frontend/
  src/                 React/TypeScript Command Center

benchmark/             benchmark protocol and research measurement assets
docs/                  implementation/research documentation
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
  -> cost estimation
  -> exhaustive / beam search
  -> hard feasibility gates
  -> Pareto candidates
  -> selected physical plan
  -> generated C++20
  -> compile/differential verification
  -> content-addressed evidence
  -> persisted experiment record
  -> evidence-grounded explanation
  -> runtime drift/adaptation control plane
```

## Evidence classes

MORPHEUS deliberately keeps these concepts separate:

- **prediction** — model output;
- **calibration measurement** — measured primitive operation under a machine/protocol;
- **artifact compile evidence** — generated code accepted by a local toolchain;
- **correctness evidence** — generated behavior compared with a reference model;
- **benchmark measurement** — end-to-end measured artifact behavior;
- **runtime recommendation** — control-plane adaptation proposal;
- **confirmed state** — control-plane state after explicit confirmation.

A stronger label must never be inferred from a weaker one.

## Important current boundaries

- `OrderedTreeIndex` is currently backed by `std::map`; it is not yet a custom production B+ tree.
- The bitmap primitive is currently a posting-vector correctness baseline rather than a compressed Roaring implementation.
- Generated mutation handling rebuilds selected indexes for correctness-first semantics.
- Compile verification is a local fixed-policy process, not a hardened sandbox.
- Runtime adaptation does not yet perform real process-level hot swap.
- SQLite + local content-addressed filesystem storage is an MVP persistence layer.
- The Copilot is deterministic evidence mode; an LLM language layer is not yet an evidence authority.
- Broad automatic data-structure synthesis, index tuning and adaptive indexing have prior art; novelty claims must be scoped to mechanisms actually demonstrated by MORPHEUS experiments.

## CI

GitHub Actions validates:

- backend Python tests;
- React/TypeScript production build;
- C++20 release build + CTest;
- C++20 AddressSanitizer + UndefinedBehaviorSanitizer profile.

See `PHASE_STATUS.md` and `progress.json` for the latest verified checkpoint rather than assuming the latest commit is green.

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

Keep Git lightweight. Do not commit generated binaries, dependency directories, large raw benchmark datasets, large traces, model checkpoints, or duplicate media. Preserve large reproducible artifacts outside Git and reference them by checksum/provenance where appropriate.

## Current research direction

The strongest MORPHEUS thesis is not a generic claim that automatic data-structure design exists for the first time. The research program is focused on a tighter integration of typed workload intent, capability algebra, calibrated compositional search, executable artifacts, explicit correctness/evidence gates, uncertainty-aware evaluation, provenance, and transition-cost-aware resynthesis.

See `docs/RESEARCH-RADAR.md` when present and `benchmark/PROTOCOL.md` for experiment discipline.
