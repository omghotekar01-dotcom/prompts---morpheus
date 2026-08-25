# MASTER PROMPT #10 — VOLUME 8: CONFIGURATION SYNTHESIS, SEARCH, PARETO OPTIMIZATION & EMPIRICAL ORACLES

## Mission
Implement MORPHEUS as an actual synthesis engine, not a rule recommender. Given WorkloadIR, machine profile, primitive registry, cost model, hard constraints and objective, construct legal composite physical configurations, select query routes, predict/measure their costs, explore the design space reproducibly and return the best supported design plus alternatives and evidence.

## 1. Formal problem
`C* = argmin_{C∈F(D,W,H)} J(C;D,W,H)` or compute Pareto set for multi-objective mode. `F` includes semantic coverage, primitive preconditions, resource/capability constraints and code-generation support. Search algorithm must not redefine correctness.

## 2. ConfigurationIR
```text
Configuration {
 ConfigurationId id;
 RecordStoreInstance primary;
 vector<PrimitiveInstance> indexes;
 map<OperationId, AccessRoute> routes;
 MaintenanceGraph maintenance;
 CanonicalHash hash;
}
```
Canonical representation is order-independent where semantics are order-independent.

## 3. Search result
```text
SearchResult {
 status: SELECTED|NO_FEASIBLE_CONFIGURATION|BENCHMARK_MORE|FAILED;
 selected?; pareto; alternatives;
 candidate_evaluations; search_stats; trace;
 model_version; registry_hash; workload_hash; machine_hash; seed;
}
```
Never return null/empty ambiguity.

## 4. Candidate evaluation
Store feasibility, rejection reasons, predicted CostVector, uncertainty, objective score or Pareto rank, benchmark evidence, generation/compile status. A rejected candidate remains useful research evidence but can be trace-sampled to control storage.

## 5. Search-space generation
Separate structural decisions from parameters and routes: choose primary store; choose zero/more indexes by field; instantiate parameters; choose legal routes per operation. Avoid generating obviously impossible combinations by capability/precondition filtering.

## 6. Coverage-first pruning
Before cost prediction ensure every required operation has correctness-preserving route. If scan fallback is allowed, represent it explicitly and cost it; do not magically assume unsupported operations work.

## 7. Hard constraints
Apply cheap exact checks early (structure count, unsupported semantics), conservative memory prediction next, expensive cost/benchmark later. Hard constraints never become penalties unless specification explicitly says soft.

## 8. Objective
Weighted objective uses versioned normalization and coefficients; Pareto mode preserves physical vectors; lexicographic mode obeys priority order. Search must consume ObjectiveDefinition interface rather than hardcode latency.

## 9. Exhaustive search
Implement first for small spaces. It is the correctness/research oracle for search algorithms. Enumerate all canonical feasible candidates, evaluate deterministically and select true model optimum; optionally benchmark all for empirical optimum.

## 10. Random search
Uniformity over representation choices is nontrivial; document sampling distribution. Seeded/reproducible. Useful baseline, not sophisticated final method.

## 11. Greedy search
Start from minimal feasible config; repeatedly apply best local mutation by predicted improvement. Define neighborhood operators explicitly. Keep as baseline and warm-start mechanism.

## 12. Beam search
Primary scalable MVP strategy. Maintain top B partial/full candidates by lower-bound/estimated score; expand canonical mutations; deduplicate; prune infeasible/dominated candidates; record beam history. Beam width is optimizer config, not workload semantics.

## 13. Neighborhood operators
Examples: add index(field,primitive); remove index; replace primitive; tune parameter; change route; switch primary store; add filter+verify route; combine bitmap routes. Every mutation yields canonical candidate and `ConfigurationDiff`.

## 14. Parameter search
Start with curated discrete grids derived from descriptor schemas. Later use local continuous/discrete tuning or Bayesian optimization. Never hide parameter choices; configuration must serialize all.

## 15. Dominance pruning
If candidate A has no worse predicted physical metrics and strictly better at least one, B can be Pareto-pruned when semantic capabilities equal/superset and uncertainty does not invalidate dominance. Be conservative with overlapping uncertainty.

## 16. Lower bounds
For partial configurations, estimate optimistic remaining cost to prioritize/prune. Lower bound must be valid if used for correctness claims; heuristic score can guide beam but must be labelled heuristic.

## 17. Symmetry/dedup
Sort semantically unordered index instances by canonical key. Hash canonical graph. Prevent duplicate routes/configs produced through different mutation sequences.

## 18. Search budget
Support max candidates, wall-clock, model evaluations, benchmark budget and memory. Termination reason stored. Search result must state whether space was exhaustive or truncated.

## 19. Determinism
Fixed WorkloadIR, machine/model/registry versions, optimizer config and seed should reproduce candidate ordering/selection modulo documented floating-point/platform caveats.

## 20. Parallel evaluation
Candidate cost predictions/benchmarks may parallelize later, but deterministic result ordering and reproducible logs must be maintained. MVP single-thread is acceptable.

## 21. Pareto frontier
Non-dominated configurations over selected metrics. Provide frontier and knee/representative suggestions without claiming a unique optimum. UI plots latency-memory-update tradeoffs.

## 22. Constraint frontier
When no feasible config exists, compute useful nearest violations: minimum achievable predicted memory, candidate closest to SLA, which hard constraint blocks all. Do not silently relax.

## 23. NO_FEASIBLE_CONFIGURATION
Return structured explanation: constraints; number candidates considered; dominant rejection categories; nearest candidates; possible user actions clearly labelled as suggestions, not automatic changes.

## 24. Empirical oracle
For tractable benchmark spaces, compile/benchmark every candidate under same generated workload. Define empirical objective and `C_emp*`. Report optimizer regret `(J_measured(C_selected)-J_measured(C_emp*))/J_measured(C_emp*)` and top-k recall.

## 25. Model oracle vs empirical oracle
Exhaustive model search finds best according to model, not reality. Keep names separate. This distinction is mandatory for papers.

## 26. Finalist reranking
After model search, select diverse/top K feasible finalists, benchmark, rerank using measured metrics according to same objective. If measurement noise overlaps, report uncertainty/tie rather than fake precision.

## 27. Search trace
Compact event stream: candidate generated, rejected reason, predicted, pruned, beam retained, benchmark requested, final selected. Use sampling/aggregation for huge runs. Trace powers UI and research debugging.

## 28. Explain selection
Produce deterministic evidence graph: workload facts → route needs → candidate components → predicted/measured metrics → constraints → objective comparison → selection. Also explain why nearest alternative lost.

## 29. Counterfactuals
Useful advanced feature: recompute ranking under changed memory/objective/workload weights without rebuilding unrelated evidence. UI can answer “What if memory were 128 MiB?” with explicit rerun/provenance.

## 30. Sensitivity
Perturb uncertain workload/model inputs and observe configuration stability. If tiny changes flip winner, report low decision stability and consider benchmark-more.

## 31. Robust search
Future: optimize worst-case or expected objective over workload uncertainty set/distribution. Configuration robust across likely workload region may beat fragile point optimum. Keep separate from MVP.

## 32. Search caching
Cache candidate predictions by `(config_hash, workload_hash, machine_hash, model_version)`. Benchmark cache additionally includes benchmark protocol/build artifact hashes. Never reuse stale model result across changed semantics.

## 33. Search database
Persist job, optimizer config, candidate summary, selected/alternatives, metrics, trace artifact pointer and hashes. Avoid storing gigantic repeated JSON; normalize/reference immutable configuration hashes.

## 34. API
`synthesize(...)`, `evaluate_configuration(...)`, `enumerate_small_space(...)`, `pareto(...)`, `explain_search(...)`, `benchmark_finalists(...)`. CLI supports `--strategy exhaustive|random|greedy|beam --seed --max-candidates --benchmark-top-k`.

## 35. Search tests
Synthetic cost landscapes with known optimum; exhaustive enumeration count; beam vs exhaustive gap; dedup invariants; hard constraint enforcement; no-feasible state; deterministic seed; Pareto correctness; route coverage; cache-key correctness; finalist rerank.

## 36. Benchmark baselines
Compare exhaustive, random, greedy, beam under equal evaluation budgets. Metrics: best objective found, empirical regret, wall time, model evaluations, memory, optimum hit rate/top-k recall.

## 37. Ablations
Disable composition; disable parameter tuning; disable machine calibration; disable uncertainty; disable finalist benchmarking; disable adaptation later. Show contribution of each subsystem.

## 38. Complexity honesty
Search space can be combinatorial. Document approximate size and explored fraction. Do not say “optimal” unless exhaustive under declared space/objective or otherwise proven. Use “selected/best found” for heuristic search.

## 39. Candidate-space definition
Research paper must publish exact primitive set, parameter grids, route rules and constraints. “MORPHEUS beat baselines” is meaningless if candidate space is hidden.

## 40. MVP
Fields: ID + numeric range; primitives: hash/B+ tree/sorted array; optional indexes; memory hard constraint; weighted latency+memory+update objective; exhaustive/random/beam; top-3 benchmark; search visualization. This proves synthesis scientifically.

## 41. Scale-up
Then trie/bitmap; multi-field filters; richer parameters; genetic/Bayesian search only after beam/exhaustive baseline is established. Fancy algorithm without oracle comparison is not progress.

## 42. Genetic search future
If used: genome is canonical configuration encoding; crossover/mutation must preserve/repair feasibility; seed and population history logged. Compare fairly against beam/random under evaluation budget.

## 43. Bayesian optimization future
Most suitable for parameter tuning over fixed structure topology, not arbitrary graph synthesis unless representation/kernel carefully designed. Do not force it for novelty.

## 44. Learning-to-search future
Use historical synthesis jobs to propose promising structures. It may accelerate search but cannot bypass semantic feasibility/correctness. Always retain deterministic fallback.

## 45. AI role
LLM may explain search results or suggest optimizer budget, but must not secretly rank candidates outside measured cost pipeline. MORPHEUS's scientific core remains explicit.

## 46. UI
Live graph/table: explored candidates, feasible count, pruning reasons, current best, Pareto frontier, benchmark status. Avoid fake “AI thinking” animations; visualize actual search trace.

## 47. Acceptance gates
Exhaustive oracle works; candidate canonicalization/dedup works; hard constraints executable; no-feasible handled; objective versioned; beam/random reproducible; Pareto correct; search budget/termination recorded; model vs empirical optimum separated; finalist benchmarking integrated; selected candidate reconstructable exactly; explanation names evidence and alternative.

## Build order
Configuration/route types → feasibility → canonicalization/hash → exhaustive → objective/Pareto → random → neighborhood operators → greedy → beam → cache/trace → finalist benchmarking → empirical oracle studies → sensitivity/robustness.

## North star
MORPHEUS's claim is not “we know which DSA is good.” Its claim is that physical representation is a search variable. Every selection must therefore be reconstructable as: declared design space + legal composition rules + measured/predicted evidence + constraints + objective + explicit search procedure.

**NEXT: MASTER PROMPT #11 — VOLUME 9: CODE GENERATION, COMPILATION, CORRECTNESS VERIFICATION & ARTIFACT PIPELINE.**
