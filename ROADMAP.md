# MORPHEUS IMPLEMENTATION ROADMAP

This roadmap is dependency-driven. Every phase ends with reproducible evidence, not a screenshot-only milestone.

## P0 — Repository constitution and engineering corpus
Deliver: prompt index, Omega master prompt, corpus manifest, truth-state vocabulary, phase/status/changelog/progress files.
Acceptance: a new implementation agent can determine scope, current state, next dependency-ready task and evidence rules without conversational memory.

## P1 — Workload language and synthesis vertical slice
Build:
- typed MWS models;
- safe YAML/JSON parser;
- semantic validation;
- deterministic canonical hash;
- primitive capability catalog;
- interpretable predicted cost functions;
- bounded exhaustive/configuration search;
- selected composite result with rejection reasons;
- FastAPI endpoints;
- generated C++ preview;
- unit/API tests.
Acceptance: canonical example returns deterministic winner; impossible constraints return explicit infeasibility; all numeric values are labelled predicted.

## P2 — Real C++ primitive laboratory
Build:
- common C++ interface;
- hash index;
- ordered/sorted index;
- trie/prefix primitive;
- bitmap/filter primitive where feasible;
- primitive registry metadata;
- deterministic tests and CMake build.
Acceptance: clean C++20 build; tests exercise insert/find/range/update behavior; no mock primitive is advertised as real.

## P3 — Generated artifact and correctness gate
Build:
- deterministic ConfigurationIR;
- template/code renderer;
- CMake artifact generation;
- reference model;
- stateful differential operation-sequence generator;
- compile/test worker boundary.
Acceptance: generated artifact compiles from clean environment and matches reference outputs/final state for replayable sequences.

## P4 — MORPHEUS Command Center UI
Build a responsive React/TypeScript systems dashboard:
- left navigation + command palette;
- workload studio;
- input -> engine -> output pipeline;
- synthesis progress/search summary;
- configuration graph;
- candidate table and elimination reasons;
- predicted cost cards with explicit evidence badges;
- generated source viewer;
- deployment panel;
- runtime/adaptation empty states until real telemetry exists;
- activity log from backend events;
- bounded copilot/explanation surface.
Acceptance: production build succeeds; keyboard/mobile/desktop layouts are usable; no fabricated live data.

## P5 — Calibration and benchmark science
Build:
- machine-profile collector;
- seeded data/workload generators;
- microbenchmark runner;
- raw observation schema;
- calibration model fit;
- held-out prediction/ranking evaluation;
- fair baselines;
- compact experiment manifests.
Acceptance: predicted vs measured values are separately represented; model-error report exists; figures can be regenerated from raw/manifest data.

## P6 — Search and composition research depth
Build:
- exhaustive small-space oracle;
- greedy and beam search;
- Pareto frontier;
- typed hard constraints;
- composite ownership/update semantics;
- search trace/provenance;
- regret/optimality-gap evaluation.
Acceptance: at least one tractable space proves search quality against empirical optimum; at least one composite configuration is correctness-tested.

## P7 — Runtime observation and adaptation
Build:
- operation counters/telemetry;
- immutable observed-workload windows;
- drift metrics;
- re-synthesis trigger;
- switching-cost model;
- hysteresis/cooldown/min-dwell;
- retain/switch decision record;
- rollback/validation path.
Acceptance: controlled phase-changing workload measures cumulative benefit including transition cost and demonstrates anti-thrashing behavior.

## P8 — Production control plane
Build:
- durable job state machine;
- isolated build/benchmark workers;
- object/artifact storage abstraction;
- authn/authz if multi-user;
- quotas and resource limits;
- structured logs/traces/metrics;
- migrations and backup/restore;
- security tests.
Acceptance: failure/retry/cancel semantics are deterministic; malicious input cannot interpolate shell/path operations; build jobs have bounded resources.

## P9 — Evidence-grounded copilot
Build:
- NL -> draft MWS;
- assumption ledger;
- validator repair loop;
- explanation from ConfigurationIR/SearchTrace/Measurements;
- experiment assistant;
- prompt-injection defenses;
- bounded tool permissions.
Acceptance: core system remains fully usable with copilot disabled; copilot cannot create or relabel measurements.

## P10 — Research package
Build:
- frozen RQs/hypotheses;
- benchmark matrix;
- ablations;
- sensitivity tests;
- statistical analysis;
- negative-results log;
- threats to validity;
- literature/prior-art matrix;
- reproducibility scripts.
Acceptance: every paper number maps to experiment ID and raw/result manifest.

## P11 — Release, patent, paper and startup package
Build:
- release manifest;
- reproducible demo;
- tutorial/docs/SDK guide;
- research paper draft;
- provisional-patent technical disclosure package (not a patentability claim);
- customer discovery and integration pilot plan;
- deployment options/licensing notes.
Acceptance: public claims are limited to evidence in the repository/reproducible artifact.

## Global design debt policy
Any shortcut must be recorded with: rationale, risk, exact replacement milestone and whether it weakens correctness, performance evidence, security or product quality.