# MORPHEUS Research Paper Draft — Evidence-First Skeleton

Status: **DRAFT — quantitative result slots intentionally unfilled until P10 campaigns are executed**

## Working title
**MORPHEUS: Evidence-Preserving Workload-to-Data-Structure Synthesis with Calibrated Composite Search and Safe Adaptation**

## Abstract — draft
Data-structure selection is usually performed manually or within narrow tuning systems, even though application workloads combine point lookups, range scans, filtering, prefix queries and mutations under hardware and memory constraints. MORPHEUS explores an end-to-end synthesis workflow in which a typed workload specification is mapped to capability-compatible primitive compositions, evaluated by an interpretable cost model optionally anchored to target-machine calibration, searched using deterministic exhaustive or beam procedures, emitted as C++20 artifacts, verified against stateful reference behavior, and recorded with explicit provenance. The system further separates runtime drift recommendations from migration authorization and maintains content-addressed evidence. This paper evaluates model fidelity, search regret, the value of composition, generated-artifact correctness and runtime adaptation under controlled workload shifts. Numerical claims are withheld from this draft until the frozen P10 benchmark protocol produces linked raw evidence.

## 1. Introduction
Modern software rarely has a single dominant access pattern. A service may perform identifier lookup, ordered scans, low-cardinality filters and prefix discovery while also accepting updates. The physically best structure for one operation may be poor for another, and the preferred design can change with memory budgets, hardware or workload phase.

MORPHEUS treats physical data-structure design as a constrained synthesis problem rather than a one-shot recommendation. Its intended contract is:

`typed workload intent -> capability filtering -> cost estimation -> constrained composition/search -> executable artifact -> correctness evidence -> measurement -> provenance -> drift analysis -> gated re-synthesis/migration`

The central engineering principle is evidence separation. Predictions are not measurements; compile success is not correctness; correctness is not performance; a runtime recommendation is not a deployed hot swap.

### Claimed contributions — evidence-gated
The final paper may claim only contributions whose release-manifest gates are satisfied. Current implementation supports the following architectural contributions, while empirical superiority remains pending:

1. A typed workload language and deterministic semantic identity for workload-driven physical-design synthesis.
2. Capability-aware composite search with hard constraints, Pareto reporting and explicit search provenance.
3. An interpretable cost model that can remain on bootstrap priors or be explicitly anchored to measured machine profiles.
4. Deterministic C++20 artifact generation with local compile and schema-derived stateful differential verification gates.
5. Content-addressed experiment artifacts, immutable decision certificates and a tamper-evident evidence ledger.
6. A runtime control protocol that separates workload-drift recommendation, verification, migration authorization, rollback and eventual data-plane switching.
7. A research harness for deterministic experiment IDs, held-out prediction evaluation, beam-vs-exhaustive regret and paired statistical analysis.

No “state of the art,” universal speedup, production hot-swap or patentability claim is currently authorized.

## 2. Problem formulation
Let workload `W` contain query families `q_i`, weights `w_i`, schema/cardinality/selectivity metadata, update pressure and hard constraints `C`. Let primitive catalog `P` expose typed capability predicates. A configuration `x` maps supported operations to one or more physical primitives and has cost vector:

`c(x, W, M) = [latency, memory, build, update, ...]`

under machine/profile `M`. MORPHEUS solves a constrained multi-objective ranking problem over capability-valid configurations. The scalar objective used for winner selection is declared by the workload, while the Pareto set remains visible to avoid hiding trade-offs.

The research evaluation separates four errors:
- **capability error** — invalid structure/operation routing;
- **cost-model error** — prediction differs from measurement;
- **search error** — heuristic fails to find the best configuration under the model;
- **deployment/adaptation error** — switching policy loses after transition cost.

## 3. System design

### 3.1 MORPHEUS Workload Specification
Describe fields, record count, operation kinds, weights, selectivity, mutation rate, hard memory/latency constraints and objective weights. Canonical serialization creates a semantic hash for provenance.

### 3.2 Primitive capability algebra
Each primitive declares operation support and implementation truth boundaries. The current laboratory includes Robin-Hood-style hashing, an ordered-tree proxy, sorted array, prefix trie and bitmap/filter correctness baseline. Unsupported or proxy semantics are explicitly recorded.

### 3.3 Calibrated cost model
The model combines interpretable priors with optional calibration measurements. Importing a calibration profile does not silently activate it. Predictions carry source labels and uncertainty.

### 3.4 Search
MORPHEUS supports bounded exhaustive enumeration and beam search, with automatic strategy selection, feasibility gates and Pareto extraction. P10 compares beam results against exhaustive bounded model oracle where tractable.

### 3.5 Code generation and correctness
The selected configuration is rendered into deterministic C++20. Compile verification uses fixed argument vectors and no shell. Stateful differential verification builds a generated artifact, executes schema-derived operations and compares behavior against a reference model. Sanitizer CI covers the core library on supported Linux runners.

### 3.6 Evidence and reproducibility
Runs, generated artifacts and manifests are linked by SHA-256. A decision certificate records the selected candidate and claim boundaries. Audit events are mirrored into a hash-chained evidence ledger. P10 experiment manifests derive stable IDs from frozen factors instead of timestamps.

### 3.7 Runtime adaptation
Observed workload windows feed drift detection and transition-cost-aware decisions with hysteresis/cooldown. A migration must be planned, shadow-built and verification-gated before control-plane commit. Real concurrent data-plane hot swap remains a separate acceptance gate.

## 4. Research questions
Use the frozen definitions in `research/EXPERIMENT-PROTOCOL.md`:
- RQ1 end-to-end design quality;
- RQ2 cost-model fidelity;
- RQ3 search quality and efficiency;
- RQ4 value of composition;
- RQ5 adaptation under drift;
- RQ6 robustness/provenance.

## 5. Experimental methodology

### 5.1 Workloads
Use point-heavy, range-heavy, filter-heavy, prefix-heavy, balanced mixed and read/write mixed families across declared sizes, selectivities, skew and update pressure.

### 5.2 Baselines
Repository baselines must be clearly separated from external specialist baselines. Strong superiority language is blocked until contemporary external baselines are frozen by version/commit/license and measured fairly.

### 5.3 Machines and compilers
Capture CPU/OS/compiler/cache/power-governor metadata where observable. Performance contrasts are paired within a machine/compiler regime. Cross-platform CI demonstrates portability but is not performance evidence.

### 5.4 Statistics
Use paired measurements, raw samples, win/tie/loss, bootstrap confidence intervals, effect size and exact sign tests. Report multiple-comparison correction for confirmatory families. Preserve failures and exclusions.

## 6. Results — reserved evidence slots

### 6.1 RQ1
**Experiment manifest(s):** `[PENDING]`  
**Raw evidence hashes:** `[PENDING]`  
**Finding:** `[PENDING — do not fill without measured evidence]`

### 6.2 RQ2
**Prediction evaluation artifact(s):** `[PENDING]`  
**Finding:** `[PENDING]`

### 6.3 RQ3
**Search-quality report(s):** `[PENDING]`  
**Finding:** `[PENDING]`

### 6.4 RQ4
**Composition ablation manifest(s):** `[PENDING]`  
**Finding:** `[PENDING]`

### 6.5 RQ5
**Runtime trace / transition-cost evidence:** `[PENDING]`  
**Finding:** `[PENDING; live hot-swap claim currently blocked]`

### 6.6 RQ6
**Correctness/replay/ledger evidence:** `[PENDING final campaign; CI evidence exists for implementation testing]`

## 7. Related work positioning
The final related-work section must avoid claiming broad novelty where automatic physical/data-structure design already exists. It should compare MORPHEUS's exact mechanism with data-structure synthesis, physical database design/index tuning, learned indexes, adaptive indexing/database cracking, uncertainty-aware tuning and LLM-assisted tuning. `docs/RESEARCH-RADAR.md` is the working prior-art map.

The intended research distinction is the integrated, evidence-preserving pipeline and the empirical behavior of calibrated composite synthesis plus correctness and adaptation gates—not the generic proposition that data structures can be selected automatically.

## 8. Threats to validity
Carry forward the full checklist in the frozen protocol. Particular current limitations include ordered-tree proxy semantics, uncompressed bitmap baseline, rebuild-heavy generated mutation paths, limited hardware diversity and the absence of proven production concurrency/hot swap.

## 9. Conclusion — draft
MORPHEUS is designed to turn data-structure selection from an opaque recommendation into a reproducible engineering decision whose assumptions, search path, generated artifact, verification state and measurements can be inspected. The final scientific conclusion must be written only after the P10 experiment manifests have been executed and their evidence bundles pass the P11 claim gates.
