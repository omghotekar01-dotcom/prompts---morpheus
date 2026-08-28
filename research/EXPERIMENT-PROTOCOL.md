# MORPHEUS P10 — Frozen Research Experiment Protocol

Status: **FROZEN PROTOCOL v1 — execution still required**  
Truth rule: this document defines what must be measured. It is not itself performance evidence.

## Research thesis

MORPHEUS is evaluated as an evidence-preserving workload-to-data-structure synthesis system: typed workload intent is converted into constrained composite physical designs, searched with interpretable/calibrated cost models, materialized as executable C++20 artifacts, correctness-gated, measured, and—where safe—reconsidered under workload drift. The evaluation must distinguish model quality, search quality, generated-artifact correctness, end-to-end performance, and runtime adaptation benefit.

## Frozen research questions and hypotheses

### RQ1 — End-to-end physical-design quality
**Question.** When all systems are run under identical workload, data, machine, compiler and memory constraints, how close is the MORPHEUS-selected design to the best measured candidate and to declared baselines?

**H1.** On heterogeneous workloads containing at least two query families, a MORPHEUS composite configuration will reduce the declared weighted objective relative to the strongest single-primitive baseline on a meaningful subset of workloads without violating hard constraints.

Primary metrics: measured weighted objective, p50/p95/p99 latency by query family, throughput, memory high-water mark, build time and update cost. Lower is better except throughput.

### RQ2 — Cost-model fidelity
**Question.** Do bootstrap and calibrated models rank candidate designs in the same order as held-out measurements?

**H2.** Explicit target-machine calibration will improve rank correlation and top-1 decision regret over bootstrap priors on held-out workloads.

Primary metrics: MAE, RMSE, MAPE where defined, signed bias, Spearman rho, Kendall tau-b, top-1 absolute/relative regret.

Frozen matrix: `research/matrices/rq2-cost-model.json`.

### RQ3 — Search efficiency vs oracle quality
**Question.** How much search work can beam search remove while retaining the exhaustive bounded-space winner/Pareto region?

**H3.** For bounded spaces in which exhaustive enumeration is feasible, tuned beam search will substantially reduce evaluated configurations while keeping median model-oracle regret near zero.

Primary metrics: evaluated/theoretical ratio, winner match rate, absolute/relative score regret, Pareto ID coverage.

Frozen matrix: `research/matrices/rq3-search-quality.json`.

### RQ4 — Value of composition
**Question.** Is the composite capability itself responsible for gains, or can a single primitive explain them?

**H4.** Removing multi-primitive composition will increase measured objective on mixed workloads where query families have incompatible primitive preferences.

Ablation: force all routable operations through one primitive at a time, subject to capability constraints.

Frozen matrix: `research/matrices/rq4-composition.json`.

### RQ5 — Runtime adaptation under drift
**Question.** Does adaptation produce net cumulative benefit after build/migration cost while avoiding oscillation?

**H5.** Under controlled phase-changing workloads, hysteresis + cooldown + transition-cost gating will outperform immediate switching and never-switch baselines on cumulative objective when phase duration exceeds the measured break-even interval.

Primary metrics: cumulative latency/throughput objective, migration cost, number of switches, rollback count, regret vs phase-aware oracle, time-to-break-even.

Frozen matrix: `research/matrices/rq5-adaptation.json`.

### RQ6 — Robustness and evidence integrity
**Question.** Does the system preserve correctness and provenance when workloads, seeds, toolchains and failure modes vary?

**H6.** Generated artifacts that pass compile + stateful differential gates will remain semantically consistent for the supported operation subset across seeded replay suites; experiment manifests and evidence chains will remain reproducibly verifiable after process restart.

Primary metrics: verification pass rate, replay mismatch count, sanitizer failures, manifest hash stability, evidence-ledger integrity.

## Benchmark matrix

The default publication matrix is intentionally broader than CI smoke testing.

| Axis | Frozen values / rule |
|---|---|
| Record count | 1e3, 1e4, 1e5, 1e6 when machine capacity permits |
| Query mix | point-heavy, range-heavy, filter-heavy, prefix-heavy, balanced mixed, read/write mixed |
| Key distribution | uniform, hotspot, Zipf-like skew |
| Selectivity | low, medium, high per supported query family |
| Update pressure | read-only, low update, medium update, high update |
| Memory constraint | unconstrained baseline, moderate cap, tight feasible cap |
| Search | exhaustive when tractable; beam widths 4, 8, 16, 32, 64, 128 |
| Calibration | bootstrap priors, target-machine calibrated profile |
| Seeds | 1337, 2027, 9001, 424242, 8675309 minimum |
| Repetitions | >= 10 for exploratory; >= 30 preferred for final paper tables unless runtime cost is prohibitive and disclosed |
| Compilers | GCC and Clang on Linux; MSVC portability validation on Windows; performance comparisons must not mix compilers within a paired contrast |

A matrix may be reduced only by an explicit resource note in the experiment manifest. CI smoke runs are never substituted for publication measurements.

## Baselines

### Implemented/available baselines
- MORPHEUS single-primitive configurations from the same capability catalog.
- `std::unordered_map`-class hash behavior through the internal hash baseline where equivalent.
- `std::map` ordered-tree proxy currently used by `OrderedTreeIndex`.
- sorted-array baseline.
- trie baseline.
- bitmap posting-vector correctness baseline.

### Required external/specialist baselines before strong superiority claims
At least one specialist implementation per relevant family should be integrated where licensing/build reproducibility permits. Candidate families include high-quality flat/robin-hood hash maps, compressed bitmaps, B-tree/B+tree variants, and specialized prefix indexes. Exact libraries must be frozen in the release manifest with commit/version/license. Until then, claims must say “against repository baselines,” not “state of the art.”

## Ablations

Every final end-to-end result set must include, where applicable:
1. no calibration (bootstrap prior only);
2. no composition (single primitive only);
3. exhaustive vs beam search on tractable spaces;
4. no uncertainty use in selection/measurement policy;
5. no hysteresis/cooldown in adaptation;
6. no transition-cost gating;
7. no runtime adaptation (static winner);
8. correctness gate disabled only in an isolated experiment to quantify gate overhead—never for production claims.

## Sensitivity studies

At minimum vary:
- beam width;
- memory cap;
- update-rate weight;
- workload-drift threshold;
- cooldown/min-dwell;
- transition-cost multiplier;
- calibration sample count;
- skew/selectivity.

Plot or tabulate both the objective and decision identity. A method is unstable if tiny parameter changes repeatedly flip winners without statistically meaningful measured differences.

## Statistical policy

1. Prefer **paired** comparisons: same machine, dataset seed, workload seed, compiler, process policy and repetition index.
2. Report median and IQR for latency distributions plus mean where useful for cumulative objectives.
3. For paired aggregate contrasts report treatment-minus/baseline-aware improvement, win/tie/loss counts, exact two-sided sign test, and deterministic bootstrap confidence intervals.
4. Report effect sizes, not p-values alone.
5. Correct families of multiple comparisons before making confirmatory claims; Holm-Bonferroni is the default implemented method.
6. Always expose raw sample count and excluded/failed runs.
7. Do not remove outliers merely because they are inconvenient. Exclusions require a predeclared mechanical rule and a logged reason.
8. Separate exploratory tuning data from held-out evaluation data.
9. Never pool measurements from different hardware into one latency average unless the analysis explicitly models machine as a factor.

The repository implementation in `backend/app/research_suite.py` provides deterministic experiment freezing, paired improvement semantics, exact sign tests, effect size and deterministic bootstrap confidence intervals. `backend/app/multiple_comparisons.py` adds deterministic Holm-Bonferroni family-wise error correction for caller-supplied p-values. Publication plotting and execution of the frozen benchmark campaigns remain follow-on work.

## Measurement discipline

Before each final campaign:
- capture machine/OS/CPU/compiler provenance;
- record CPU governor/power plan when observable;
- avoid competing heavy processes;
- warm up according to protocol;
- use monotonic clocks;
- preserve raw per-repetition values;
- pin generated source hash, primitive source commit and experiment manifest hash;
- keep calibration and evaluation seeds disjoint where feasible;
- record failed runs rather than silently re-running until success.

## Negative-results policy

Negative results are mandatory research output. Record:
- workloads where MORPHEUS loses to a simple baseline;
- workloads where composition adds overhead without benefit;
- beam widths with unacceptable regret;
- calibration profiles that worsen ranking;
- adaptation scenarios that fail to repay switching cost;
- correctness or portability failures;
- machine/toolchain-specific anomalies.

A negative result may narrow a claim, motivate a mechanism, or invalidate a hypothesis. It must not be deleted from the evidence trail.

## Threats to validity checklist

### Internal validity
- benchmark harness overhead;
- cache warm/cold state;
- background OS noise;
- compiler flags;
- accidental seed leakage;
- calibration/test overlap;
- measurement order effects.

### Construct validity
- weighted objective may not represent a real application;
- model p99 proxy is not measured p99;
- `std::map` is not a B+ tree;
- posting-vector bitmap is not a compressed bitmap;
- generated mutation paths may overstate or understate write cost until measured under realistic write pressure.

### External validity
- limited hardware diversity;
- synthetic workload distributions;
- unsupported query families;
- small primitive catalog;
- lack of production concurrency/NUMA/storage effects.

### Conclusion validity
- low sample counts;
- multiple comparisons;
- heavy-tailed latency;
- non-independent repeated measurements;
- reporting only winner workloads.

## Claim gates

A statement may appear in a paper, patent disclosure, demo, pitch or README only when its evidence class is satisfied:

| Claim | Minimum evidence |
|---|---|
| “MORPHEUS generates C++20” | stored generated artifact hash |
| “artifact compiles” | compile verification manifest |
| “artifact is correct for supported routes” | stateful differential verification manifest + replay identity |
| “X% faster” | frozen experiment ID + raw measured samples + baseline identity + machine profile + statistical summary |
| “beam search preserves quality” | bounded exhaustive oracle comparison over declared matrix |
| “calibration improves decisions” | held-out paired prediction/ranking evaluation |
| “runtime adaptation helps” | measured phase-changing workload including migration cost |
| “native local version switching works” | in-process atomic publication/rollback evidence with concurrent reader stress and logical snapshot rebuild; current implementation satisfies only this narrower local claim |
| “cross-configuration/process hot swap works” | real generated-object cross-configuration/process migration/swap/rollback evidence under concurrent access; currently **not satisfied** |
| “state of the art” | strong contemporary external baselines and reproducible superiority; currently **not satisfied** |
| “patentable” | legal/patent review; repository engineering alone cannot establish patentability |

## P10 completion acceptance

P10 becomes `VALIDATED_RESEARCH_PACKAGE` only after all of the following are present:
- frozen RQs/hypotheses;
- deterministic experiment manifest tooling;
- benchmark matrix with machine provenance;
- ablation and sensitivity manifests;
- paired statistical analysis;
- multiple-comparison correction for confirmatory claim families;
- negative-results log;
- threats-to-validity record;
- at least one complete measured campaign for RQ1–RQ4;
- controlled measured adaptation campaign for RQ5 or an explicit blocked status;
- every paper-facing number linked to raw samples and experiment ID;
- CI verifies analysis tooling and manifest determinism.
