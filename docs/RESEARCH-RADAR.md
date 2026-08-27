# MORPHEUS Research Radar

Last updated: 2026-08-27

## Purpose
This document prevents MORPHEUS from making broad novelty claims that are already covered by established database and data-structure research. It maps nearby prior art, identifies the narrower mechanisms that remain scientifically interesting, and defines the experiments required before paper or patent claims become credible.

## Prior-art boundaries

### Automatic data-structure design
The Data Calculator and related data-structure design-space work already established that composable primitives, workload/data/hardware inputs and learned/analytical cost models can be used to synthesize or navigate data-structure designs. MORPHEUS must not claim that automatic data-structure synthesis itself is new.

### Physical database design and index tuning
AutoAdmin, Database Tuning Advisor and many later systems establish automatic index/physical-design recommendation as mature prior art. MORPHEUS novelty must therefore live beyond a generic "AI chooses indexes" framing.

### Adaptive indexing
Database cracking, stochastic cracking and later adaptive indexing work establish workload-driven physical reorganization and online adaptation. MORPHEUS must not claim that adapting indexes to workload change is generically new.

### Workload-aware learned indexes
Recent workload-aware learned-index research already monitors workload behavior and adapts learned structures. MORPHEUS must distinguish itself through the breadth of its typed capability composition, executable artifact gates, transition-cost accounting, provenance and cross-primitive synthesis rather than the mere presence of workload awareness.

### LLM-driven index tuning
Recent evaluations show that LLM index recommendations can sometimes discover useful alternatives but may be variable, expensive to validate and less reliable than mature tuning advisors. MORPHEUS therefore treats an LLM as an optional language/proposal/explanation layer, never as the benchmark or evidence authority.

### Uncertainty-aware tuning
Recent index-tuning work already studies uncertainty quantification and active learning. MORPHEUS uncertainty must affect engineering behavior: which candidates are benchmarked, when calibration is requested, how confidence is reported and when search results are withheld from strong claims.

## Working MORPHEUS research thesis
A defensible MORPHEUS thesis is the integration of:

1. a typed workload-intent language;
2. an explicit capability algebra across heterogeneous primitive families;
3. calibrated compositional search with hard feasibility gates;
4. uncertainty-aware candidate ranking and measurement allocation;
5. executable generated artifacts rather than recommendation-only output;
6. compile, differential correctness and benchmark evidence gates;
7. content-addressed provenance linking specification, candidate, source, toolchain and measurements;
8. workload-drift detection with explicit switching-cost and hysteresis logic;
9. a safe migration path that can eventually shadow-build, validate, swap and roll back;
10. an evidence-grounded Copilot whose language cannot silently upgrade predictions into measurements.

The research question is not "can software choose a data structure?" The research question is whether this integrated pipeline can produce useful designs with predictable decision quality, reproducible evidence and safer adaptation than narrower recommendation-only or single-index approaches.

## Research questions

### RQ1 — Prediction quality
How accurately does the MORPHEUS cost model rank candidate physical designs on held-out workloads and machines?

Required metrics:
- MAE;
- RMSE;
- MAPE where meaningful;
- signed bias;
- Spearman rho;
- Kendall tau-b;
- top-1 decision regret;
- top-k oracle coverage;
- calibration/error stratified by primitive and operation.

### RQ2 — Search quality
How much quality does beam search lose relative to exhaustive search on bounded spaces, and how much search cost does it save?

Required outputs:
- evaluated configurations;
- wall-clock search time;
- winner objective;
- objective regret relative to exhaustive oracle;
- Pareto coverage;
- failure cases by workload shape.

### RQ3 — Composition value
When does a composite design outperform the best single-primitive baseline under the same hard constraints?

Required ablation:
- best single primitive;
- best hand-authored specialist composition;
- MORPHEUS composition;
- MORPHEUS with calibration removed;
- MORPHEUS with uncertainty ignored.

### RQ4 — Evidence-gate value
How often do generated candidates fail compile, differential correctness, sanitizer or benchmark gates, and what classes of generator/search defects are caught by each gate?

### RQ5 — Adaptation value
Under phase-changing workloads, does transition-cost-aware adaptation improve long-horizon cost compared with:
- never switch;
- immediately switch on drift;
- periodic resynthesis;
- oracle switch timing?

Measure:
- cumulative latency/work cost;
- rebuild/migration cost;
- number of switches;
- rollback count;
- time spent in degraded states;
- false-positive drift events.

### RQ6 — Provenance and reproducibility
Can an experiment be reproduced from persisted MWS, semantic hash, candidate ID, generated source hash, compiler/toolchain metadata, calibration profile and benchmark protocol without relying on hidden state?

## Baselines
At minimum, experiments should include fair baselines appropriate to the workload:

- `std::unordered_map`;
- `std::map`;
- sorted vector / binary search;
- trie/reference prefix index;
- posting-list or bitmap baseline;
- specialist libraries when license and reproducibility permit;
- best single MORPHEUS primitive;
- exhaustive MORPHEUS oracle on bounded spaces;
- beam MORPHEUS search;
- static no-adaptation policy;
- greedy adaptation policy without switching-cost/hysteresis.

A baseline must receive the same dataset, operation trace, warmup policy, compiler mode and machine conditions.

## Required experiment discipline
Every quantitative result should preserve:

- source commit SHA;
- MWS semantic hash;
- generated artifact SHA256;
- compiler identity/version and flags;
- OS/kernel and CPU model;
- logical/physical core count;
- memory capacity;
- CPU governor/power mode where controllable;
- affinity/pinning policy;
- dataset seed;
- trace seed;
- warmup count;
- repetition count;
- raw samples;
- median/mean/stdev/min/max;
- benchmark protocol version;
- calibration profile ID;
- evidence-state label.

CI timing is a correctness/smoke signal, not publication-grade performance evidence.

## Paper/patent truth table

| Claim type | Allowed now? | Minimum evidence required |
|---|---:|---|
| MORPHEUS parses typed workload specifications | Yes | tests |
| MORPHEUS searches composite candidates | Yes | tests |
| MORPHEUS generates C++20 | Yes | generated artifact tests |
| MORPHEUS compile-verifies generated code | Yes, scoped | compiler gate evidence |
| MORPHEUS generated behavior is generically correct | Not yet | broad differential/property/fuzz evidence |
| MORPHEUS is faster than standard structures | No | controlled benchmark campaign |
| MORPHEUS beam search preserves near-oracle quality | No | exhaustive-vs-beam experiments |
| MORPHEUS adapts safely at runtime | Not yet | real migration/swap/rollback implementation + stress tests |
| MORPHEUS is the first automatic data-structure synthesis system | No | contradicted by prior art |
| A specific integrated MORPHEUS mechanism is novel | Undetermined | professional prior-art search + narrow claim construction + experiments |
| Patent filed/granted | No | actual filing/grant evidence |
| Paper accepted/published | No | actual venue decision/publication evidence |

## Research implementation status
Implemented foundations:
- calibration protocol v2;
- deterministic/exhaustive/beam search provenance;
- Pareto extraction;
- prediction-source and uncertainty fields;
- persistent run/artifact/audit evidence;
- local compile gate;
- generated-artifact stateful differential test for multiple query types;
- P10 prediction evaluator with ranking and regret metrics;
- sanitizer build profile in CI.

Still required:
- broad property/fuzz testing;
- benchmark orchestration and raw-result persistence;
- machine-profile capture;
- held-out workload suite;
- beam-vs-exhaustive study;
- specialist baseline adapters;
- statistical analysis scripts;
- real runtime migration/hot-swap experiments;
- reproducibility bundle generator;
- claim-by-claim prior-art review.

## Governing rule
Every major MORPHEUS research claim must have four things attached to it:

**mechanism -> nearest prior art -> ablation/baseline -> falsifiable evidence**

If any of those four is missing, the claim remains a hypothesis rather than a result.
