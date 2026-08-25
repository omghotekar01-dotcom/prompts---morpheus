# MASTER PROMPT #5 — V03: FORMAL THEORY & MATHEMATICAL MODEL

Formalize MORPHEUS as constrained multi-objective physical-design synthesis.

## Universe
Let D = dataset/schema/statistics, W = workload, H = machine profile, P = primitive library, R = hard/soft constraints, O = objective and C = physical configuration.

Static problem:
`C* = argmin_{C in F(D,W,H)} J(C;D,W,H)`
where F is the feasible set satisfying semantics/capabilities/hard constraints.

## Dataset/workload
Represent fields with type, size, cardinality, uniqueness, stored distribution and access distribution. Operations carry kind, target fields, frequency/rate, selectivity/hit rate and update behavior. Preserve both relative mix and absolute rate when known.

## Configuration
A configuration contains primary storage, zero or more secondary structures, typed primitive parameters and operation routing. Canonicalize/hash configurations so equivalent designs deduplicate.

## Cost vector
Preserve latency by operation, memory, update cost, build cost and supported secondary metrics before scalarization. Weighted objective may use explicit normalization; also support Pareto and lexicographic modes. Hard constraints are applied before ranking.

## Cost prediction
True cost is expensive; estimate using analytical priors + empirical calibration. Prediction records mean/estimate, uncertainty, source/model version and extrapolation status. Evaluate absolute error and ranking/top-k quality separately.

## Search
Candidate space grows combinatorially. Implement exhaustive search as ground truth on small spaces; random/greedy/beam as scalable baselines/strategies. Measure optimality regret and convergence against exhaustive empirical optimum.

## Dynamic model
For workload sequence W_t choose C_t minimizing total runtime plus transition cost:
`min sum_t J(C_t,W_t) + sum_{t>1} S(C_{t-1},C_t)`.
A switch requires expected future savings to exceed rebuild/migration/risk margin; use hysteresis/cooldown to avoid oscillation.

## Robustness
When workload/model is uncertain, permit risk-adjusted or worst-case objectives. Decision confidence must come from model uncertainty, candidate margin, calibration coverage and direct finalist measurements—not invented percentages.

## Correctness
Generated implementation G must be behaviorally equivalent to reference ADT for all supported operation sequences. Correctness is a feasibility condition, never another weighted objective.

## Provenance
Every decision pins workload hash, machine profile, primitive versions, model, search policy/seed, compiler/toolchain and benchmark protocol.

## Required software types
WorkloadIR, FieldIR, OperationIR, PrimitiveManifest/Instance, ConfigurationIR, CostVector/Estimate, ConstraintSet, Objective, SearchResult, Measurement, MigrationEstimate and AdaptationDecision.

## Deliverable
Translate every mathematical variable into an operational source: user specification, derived statistic, machine profile, benchmark or model. Do not include terms that cannot be measured/estimated transparently.

# END MASTER PROMPT #5
