# MASTER PROMPT #9 — VOLUME 7: EMPIRICAL COST MODEL, HARDWARE CALIBRATION, UNCERTAINTY & ACTIVE MEASUREMENT

## Mission
Build MORPHEUS's evidence engine. The optimizer must predict latency, memory, update/build/migration cost for candidate configurations under a concrete WorkloadIR and machine, while explicitly representing prediction uncertainty and validating finalists empirically. The project source already requires cost models based on microbenchmarks and warns that inaccurate models must be mitigated with extensive measurement/calibration. Turn that into a reproducible scientific subsystem.

## 1. Never confuse four things
Keep separate: theoretical complexity; measured benchmark samples; fitted/predicted cost; optimizer objective score. Big-O is not latency. A regression estimate is not a measurement. A weighted objective is not a physical unit.

## 2. Core interfaces
```text
CostModel.predict(Configuration, WorkloadIR, MachineProfile) -> CostPrediction
CostPrediction { CostVector mean; Uncertainty uncertainty; EvidenceQuality quality; ModelVersion model; FeatureVector features; }
CostVector { lookup/read metrics; write metrics; memory_bytes; build_ns; optional throughput; migration inputs; }
```
Objective module later converts CostVector to scalar/Pareto ranking.

## 3. Decomposition
Predict operation-specific cost first, then workload aggregate. For operation o with probability p_o and route r_o:
`E[L]=Σ p_o E[L(o,r_o)]`.
Preserve per-operation p50/p95/p99 predictions only if model/data support them; do not derive tail latency from mean by arbitrary multiplier.

## 4. Composite configuration cost
Include route primitive costs, record-store access, intersections/verifications, write maintenance across all affected indexes, memory of all components, build time and temporary memory. Account for shared work exactly once. Start with additive approximations, measure residual interaction error and improve only where evidence justifies it.

## 5. MachineProfile
Versioned immutable profile containing CPU model/architecture/features, logical/physical cores, cache hierarchy, RAM, OS/kernel, compiler/version/flags, allocator, relevant frequency policy and benchmark environment. `machine_profile_hash` participates in model/evidence provenance.

## 6. Calibration suite
Measure machine primitives useful across DSAs: sequential/random memory access, cache-sensitive pointer chasing, memcpy, integer/string hashing, comparisons, allocation, branch-heavy loops. These do not replace DSA benchmarks; they provide hardware features and sanity baselines.

## 7. Primitive microbenchmarks
For each primitive sample across N, key width/type, cardinality, hit rate, selectivity, skew, mutation ratio and primitive parameters. Record build, lookup/filter/range/prefix, insert/delete/modify and memory separately.

## 8. Experimental design
Avoid naive full Cartesian explosion. Begin with logarithmic N scales and boundary/representative parameter points. Use Latin-hypercube/random/design-of-experiments or active measurement later. Always include edge regimes where ranking may flip.

## 9. Benchmark rigor
Fixed seeds; warmups; repeated samples; correctness check; dead-code-elimination prevention; stable compiler flags; CPU affinity where feasible; avoid concurrent noisy jobs; record temperature/frequency if available; capture raw distributions. Do not promise nanosecond precision on noisy environments.

## 10. Evidence schema
```text
BenchmarkSample {
 benchmark_id; primitive/configuration hash; machine hash;
 workload_point; parameters; compiler/build hash;
 seed; repetition; warmup; cache_mode;
 metric; value; unit; timestamp; protocol_version;
}
```
Store raw samples in compact artifacts (CSV/Parquet) and metadata in experiment DB. Never put massive raw benchmark datasets into the lightweight prompt repository.

## 11. Model families
Start interpretable: analytic formulas + calibrated coefficients; piecewise linear/log models; linear/ridge regression on transformed features; tree boosting only when justified. Deep neural cost model is not automatically better. Compare using held-out error and ranking quality.

## 12. Feature engineering
Potential features: log N, key bytes, cardinality ratio, selectivity, hit rate, skew exponent/hotset, load factor, tree height/fanout, expected result count, prefix length, bitmap density, record bytes, cache sizes, memory-to-cache ratios, compiler family. Derive features deterministically and version their definitions.

## 13. Memory model
Prefer exact/structural formulas where possible, calibrated for allocator/alignment overhead. Validate predicted allocated bytes against measured. Hard memory feasibility should use conservative prediction/upper bound when uncertainty is meaningful.

## 14. Build/update models
Runtime adaptation requires these. Model build time as function of N/key/data distribution/parameters; update cost by operation and indexed fields. Peak migration memory = current + candidate + temporary overhead unless migration strategy proves lower bound.

## 15. Uncertainty
Every prediction should eventually provide uncertainty: interval, standard error/quantile, ensemble spread or empirical residual bucket. At minimum classify evidence quality `HIGH/MEDIUM/LOW/EXTRAPOLATED`. Never present an extrapolated 100M-record estimate with same confidence as measured 1M region.

## 16. Extrapolation detection
Track training-domain bounds per feature. Mark prediction extrapolated if outside calibrated region or novel categorical machine/primitive version. Search may penalize or request measurement.

## 17. Constraint safety
For hard upper-bound constraint (memory/latency), use conservative estimate such as upper confidence bound when model supports it. If confidence is insufficient, candidate can be `UNKNOWN_FEASIBILITY` and trigger benchmark-more rather than silently passing.

## 18. Calibration metrics
Report MAE, median absolute percentage error where denominator safe, RMSE/log error as relevant, R² only as supplementary, interval coverage, Spearman/Kendall ranking correlation, top-k empirical-optimum recall and configuration-selection regret. Ranking quality matters more than pretty regression fit.

## 19. Configuration-level validation
Primitive-level accuracy does not guarantee composite accuracy. Benchmark full generated configurations and compare predicted vs measured aggregate metrics. Fit interaction corrections only after systematic residual evidence.

## 20. Finalist benchmarking
Search may be model-driven, but top K feasible candidates should be compiled/benchmarked under actual workload where budget permits. Store `MODEL_SELECTED` vs `BENCHMARK_VALIDATED` explicitly. Final choice can rerank finalists by measured objective.

## 21. Exhaustive oracle studies
For small candidate spaces, benchmark every candidate. Compute true empirical optimum and optimizer optimality gap/regret. This is a core research result and protects against self-congratulatory benchmark selection.

## 22. Baseline calibration
Benchmark external baselines under identical harness/workload/machine/compiler. Do not compare MORPHEUS warm-cache optimized code against cold/noisy baseline.

## 23. Active measurement
Given uncertainty and benchmark cost, choose next experiment that maximally improves decision quality. Conceptually:
`e* = argmax_e [ExpectedValueOfInformation(e) - MeasurementCost(e)]`.
MVP heuristic: benchmark candidate when top predictions overlap within uncertainty or prediction is extrapolated near decision boundary.

## 24. BENCHMARK_MORE state
Optimizer/adaptation may return `BENCHMARK_MORE` instead of pretending confidence. Trigger reasons: close top candidates, hard constraint uncertainty, extrapolation, model disagreement, high migration stakes.

## 25. Online calibration
Runtime measured operation latencies can update machine/workload-specific residuals, but do not contaminate global model without provenance/validation. Maintain base model + local calibration layer. Version every update.

## 26. Drift
Monitor prediction residual drift and hardware/environment changes. If residual distribution shifts materially, invalidate or downgrade calibration confidence and schedule targeted recalibration.

## 27. Model registry
Store model ID/version, training dataset hashes, primitive versions, machine scope, feature schema version, algorithm/hyperparameters, validation metrics, training commit and creation timestamp. Models are immutable; promotion points to version.

## 28. Reproducible training
Training command consumes immutable evidence manifest + config + seed and emits model artifact + metrics + manifest. Same inputs should be reproducible within documented numerical tolerance.

## 29. Leakage prevention
Split calibration data by meaningful groups. If evaluating cross-N interpolation, hold out N regimes. For cross-machine claims, hold out machines. Repeated samples from same exact benchmark point must not leak into both train/test and inflate accuracy.

## 30. Statistical reporting
Report sample counts and dispersion; confidence intervals where appropriate; multiple machines/workloads for general claims. Avoid “40% faster” unless experimental protocol, baseline and uncertainty support it. Source documents' performance numbers are targets/examples until measured.

## 31. Objective normalization
Cost model emits physical metrics. Objective layer normalizes. Recommended baseline-relative dimensionless terms, e.g. latency ratio to reference. Version normalization. Never add nanoseconds + bytes directly.

## 32. Pareto support
Expose physical cost vectors so Pareto frontier can be computed without scalarization. Include uncertainty-aware visualization; a candidate may be apparently dominated only within noise.

## 33. Cost explanation
For every prediction expose top contributors: operation mix, route, primitive parameters, memory components, write maintenance, build estimate, evidence region and confidence. Explanation is generated from model features/results, not free-form speculation.

## 34. Storage
Suggested:
```text
experiments/{manifests,results}/
models/cost/{registry metadata only or external artifacts}/
backend/app/cost_model/
core/include/morpheus/cost/
```
Large binaries/raw data belong in releases/object storage/LFS only if intentionally enabled; keep normal Git lean.

## 35. APIs
`predict`, `predict_batch`, `explain_prediction`, `model_info`, `calibration_status`, `benchmark_candidate`, `compare_prediction_measurement`. Search must batch predictions for efficiency.

## 36. Tests
Unit: feature derivation, unit conversions, aggregation, uncertainty propagation. Golden: fixed model+IR+configuration yields stable prediction. Synthetic: known analytic oracle verifies ranking. Integration: train tiny model from fixture, predict, benchmark fixture, record residual. Property: memory nonnegative; increasing duplicate indexes cannot reduce structural memory absent explicit sharing; probabilities aggregate correctly.

## 37. Failure handling
Missing model: fallback only to explicitly registered baseline analytic model and mark low confidence. Corrupt artifact: fail. Unknown primitive/model feature: capability error. NaN/inf: reject prediction. Negative latency/memory: invariant failure. No silent zeros.

## 38. MVP
Three primitives; one machine; N grid; point/range/insert; memory; build; median latency; interpretable fitted models; top-3 finalist benchmarking; predicted-vs-measured plot; exhaustive small-space oracle. This is enough for credible first paper/demo.

## 39. Research questions
RQ1 prediction error across workloads; RQ2 top-k optimum recall; RQ3 selected-config regret vs exhaustive empirical oracle; RQ4 cross-machine ranking changes; RQ5 active calibration measurements needed for near-optimal selection; RQ6 uncertainty-aware selection vs point-estimate selection.

## 40. Acceptance gates
Raw benchmark samples retained; machine/compiler/protocol recorded; model/data versioned; held-out evaluation exists; ranking metrics reported; extrapolation detectable; configuration-level validation exists; hard constraints use safe semantics; top candidates benchmarkable; model-selected vs measured separated; no performance claim lacks evidence provenance.

## Build order
Benchmark protocol → MachineProfile → evidence schema → primitive benchmark adapters → data collection → feature schema → analytic baseline → fitted models → validation metrics → batch predictor → configuration aggregation → uncertainty/extrapolation → finalist benchmark → active measurement → online residual calibration.

## North star
MORPHEUS should be able to say not only “CFG-X is predicted fastest,” but “CFG-X is predicted to minimize this objective on machine H under workload W; the prediction is supported by evidence E, uncertainty U, and finalist benchmark B. Where confidence is insufficient, measure rather than bluff.”

**NEXT: MASTER PROMPT #10 — VOLUME 8: CONFIGURATION SYNTHESIS, SEARCH, PARETO OPTIMIZATION & EMPIRICAL ORACLES.**
