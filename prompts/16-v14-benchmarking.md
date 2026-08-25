# MASTER PROMPT #16 — V14: BENCHMARKING, DATASETS, CALIBRATION & EXPERIMENT INFRASTRUCTURE

Build the empirical backbone required to make MORPHEUS scientifically credible. Predictions and measured results must never be conflated.

## Benchmark layers
1. Primitive microbenchmarks: lookup/range/prefix/update/build/memory across N, cardinality, skew, selectivity and parameters.
2. Composite benchmarks: multiple structures, update propagation and routing.
3. End-to-end workloads: complete MWS mixes.
4. Adaptation experiments: phase changes, detection delay, rebuild/migration and hysteresis.

## Protocol
Pin hardware/software environment, CPU governor where controllable, compiler/flags, seed, dataset hash, warmup, repetitions and cache mode. Record raw observations plus summary statistics. Do not report only best runs. Separate setup/build from steady-state query time.

## Timing
Use appropriate monotonic/high-resolution clocks; batch extremely short operations to reduce timer overhead; prevent dead-code elimination; consume results; report ns/op or ops/s with method documented. Capture p50/p95/p99 where enough samples exist.

## Memory
Define memory metric precisely: payload, auxiliary structure bytes, allocator overhead and peak build memory. Prefer direct instrumentation plus OS process metrics; never label a theoretical estimate as measured RSS.

## Dataset generator
Deterministically generate numeric/string records with uniform, Zipf/hotset, categorical, histogram and supported empirical profiles. Preserve cardinality and uniqueness constraints. Emit dataset manifest with generator version and seed.

## Workload generator
Sample operations from resolved MWS; support hit/miss ratio, access skew, selectivity, prefix length and updates. Generate trace artifacts for replay. Validate generated empirical mix against target within tolerance.

## Calibration matrix
Cover logarithmic N, representative cardinality ratios, selectivities, skew values, key sizes and primitive parameters. Use space-filling/adaptive sampling later to reduce calibration cost. Track extrapolation distance for predictions outside calibrated domain.

## Statistics
Report repetitions, mean/median, standard deviation, confidence intervals and robust summaries. Use paired comparisons where appropriate. Correct for multiple comparisons when making broad statistical claims. Publish raw data sufficient to recompute figures.

## Baselines
Include language/library baselines and strong domain-relevant single-structure/composite baselines. Baselines use equivalent semantics, optimization flags and correctness requirements. Never sabotage competitors with poor tuning.

## Reproducibility
One experiment manifest must reproduce command, workload, candidate, dataset, machine, compiler, model and seeds. Results are append-only. Generate tables/plots from raw data by scripts—not hand-edited numbers.

## CI tiers
Smoke benchmarks on every relevant change; stable small performance suite on main; full calibration/research suites scheduled or manually triggered. Performance regressions need thresholds robust to noise.

## Deliverable
Implement benchmark harness, generators, trace replay, calibration runner, manifest schema, raw-result format, statistical analysis scripts, baseline adapters, CI suites and experiment documentation. A paper figure must be traceable to raw measurements and exact code revision.
