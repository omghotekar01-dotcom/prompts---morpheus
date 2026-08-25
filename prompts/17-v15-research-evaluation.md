# MASTER PROMPT #17 — V15: RESEARCH METHODOLOGY, BASELINES, ABLATIONS & SCIENTIFIC EVALUATION

Turn MORPHEUS from an impressive system into a falsifiable research program. Do not start with desired conclusions; define hypotheses, protocols and failure criteria first.

## Core questions
RQ1: Can workload-aware synthesis select physical data-structure configurations that outperform strong fixed baselines under mixed operations and resource constraints?
RQ2: How close does search come to the empirical optimum on small enumerable spaces?
RQ3: How accurate/calibrated is the cost model across workloads and machines?
RQ4: Which components (composition, machine calibration, finalist measurement, uncertainty, adaptation) contribute value?
RQ5: Under workload drift, when does adaptation improve total utility after rebuild/migration cost?

## Hypotheses
Write directional hypotheses with metrics before running final experiments. Define counterexamples and conditions under which MORPHEUS should not win.

## Workload matrix
Evaluate point-heavy, range-heavy, prefix-heavy, low-cardinality filtering, write-heavy, memory-constrained, skewed and phase-changing workloads across multiple N. Include synthetic controlled workloads plus at least one realistic trace/dataset if legally and reproducibly obtainable.

## Baselines
Strong STL/standard-library choices; individually tuned hash/tree/sorted/trie/bitmap implementations where applicable; simple expert heuristic; best single primitive; best manually permitted composite; exhaustive empirical optimum on small spaces. Add external systems only when semantics and comparison are defensible.

## Metrics
Weighted latency, per-operation latency, throughput where supported, p50/p95/p99, memory, build time, update cost, search time, candidate count, prediction error, regret vs empirical optimum, Pareto hypervolume where justified, adaptation detection/switch cost and cumulative utility.

## Ablations
Remove one mechanism at a time: no composition, no machine calibration, analytical-only model, no finalist benchmarking, no uncertainty penalty, greedy vs beam/exhaustive, no hysteresis, no adaptation. Keep all other conditions fixed.

## Search-quality proof
For small spaces enumerate every valid ConfigurationIR and benchmark them. Compare heuristic winner to empirical best and report regret/distribution—not cherry-picked successes.

## Cost-model evaluation
Train/calibrate without test leakage. Report MAE/MAPE carefully (avoid MAPE near zero), rank correlation, top-k selection accuracy and calibration/coverage of uncertainty intervals. Evaluate interpolation separately from extrapolation.

## Statistical discipline
Use repeated trials, confidence intervals and effect sizes. State sample counts. Prefer paired tests for same workload/machine. Correct multiple testing when needed. Report negative results.

## Threats to validity
Explicitly discuss synthetic workload realism, implementation quality, machine dependence, benchmark noise, limited primitive library, search-space definition, compiler effects and generalization.

## Artifact evaluation
Provide scripts/configs to regenerate core tables and figures from manifests/raw results. Pin dependencies and include compact sample data where licensing permits.

## Deliverable
Produce an experiment registry, RQ/hypothesis document, workload matrix, baseline matrix, ablation plan, statistical analysis plan, figure/table plan, threats-to-validity template and reproducible execution scripts. No scientific claim may exceed the evidence collected.
