# MASTER PROMPT #12 — VOLUME 10: RUNTIME MONITORING, WORKLOAD DRIFT, HYSTERESIS, MIGRATION & SAFE ADAPTATION

## Mission
Implement MORPHEUS's defining dynamic layer: observe actual workload, detect meaningful change, reevaluate physical configurations and switch only when expected future benefit exceeds transition cost and safety margin. The source design explicitly states `PredictedBenefit > λ × SwitchingCost + SafetyMargin` to prevent thrashing. Turn this into a measurable, conservative state machine—not a flashy auto-switch demo.

## 1. Separation
Original WorkloadIR is immutable declared intent. Runtime creates `ObservedWorkloadSnapshot` and telemetry. Adaptation compares declared/current observations; it never rewrites history.

## 2. Runtime state
```text
RuntimeState {
 current_configuration_hash;
 artifact_id;
 workload_snapshot;
 performance_snapshot;
 machine_profile_hash;
 last_transition;
 adaptation_state;
}
```

## 3. Telemetry
Per operation: count/rate, latency samples/histograms, hit rate, result cardinality/selectivity estimates, errors. Writes: insert/delete/modify counts and affected fields. System: memory, build/migration metrics where available. Keep telemetry bounded/aggregated.

## 4. Observation windows
Support fixed time or operation-count windows. Store window boundaries/sample count. Use exponentially weighted estimates only if semantics documented. Avoid decisions on tiny samples.

## 5. Drift detection
Start interpretable: change in operation-mix distance, rate ratio, selectivity/hit-rate shifts and sustained latency residual. Later use statistical change-point methods. Drift is evidence to reevaluate, not automatic permission to switch.

## 6. Drift thresholds
Versioned policy with minimum samples, threshold, persistence windows and cooldown. Test false-positive/false-negative tradeoffs using synthetic phase workloads.

## 7. Reoptimization
On sustained drift, create a new optimization context using same dataset/machine plus observed workload snapshot and current configuration. Search returns alternatives with transition-aware evaluation.

## 8. Transition cost
```text
MigrationEstimate {
 build_time; copy_time; validation_time; cutover_time;
 peak_memory; temporary_storage;
 expected_downtime;
 rollback_cost;
 uncertainty;
}
```
MVP may estimate stop-the-world/offline rebuild; label it honestly.

## 9. Benefit horizon
A switch only makes sense over expected horizon `T_H`. Estimate cumulative benefit `(current_cost - candidate_cost) × expected_future_work`. Horizon may be configured or inferred conservatively; uncertainty must be surfaced.

## 10. Decision rule
Implement configurable policy equivalent to:
`Benefit > λ·SwitchingCost + SafetyMargin` plus hard safety constraints. `λ≥1` expresses conservatism. Include uncertainty: compare lower confidence bound of benefit to upper bound of transition cost when available.

## 11. Decision actions
`STAY`, `SWITCH`, `BENCHMARK_MORE`, `PREBUILD` (future), `ROLLBACK` (post-failure). Every action stores reason, evidence and policy version.

## 12. Hysteresis
Use separate enter/exit thresholds or explicit switching penalty/cooldown so noisy workload near boundary does not oscillate. Measure switch count/thrashing in experiments.

## 13. Cooldown
After switch, suppress ordinary reevaluation for configured window unless safety failure occurs. Do not mask severe correctness/health events.

## 14. Candidate validation
Before switching: configuration semantic/capability feasibility; generated artifact compiled; correctness tests passed; hard memory incl. peak migration; optional finalist benchmark; compatibility with runtime facade.

## 15. Migration strategies
Phase A MVP: offline/restart rebuild. Phase B: shadow build candidate while current serves traffic, validate, atomic pointer/facade cutover. Phase C: incremental migration/hot swap if rigorously implemented. Never claim C while running A.

## 16. Shadow build
Build candidate from consistent snapshot; apply/capture intervening writes or pause cutover depending design; validate record counts/checksums/sample queries; cut over atomically. Define memory peak.

## 17. Consistency
During migration no committed record may disappear/diverge between logical store and indexes. Single-thread MVP can use global lock. Concurrency later requires explicit synchronization/versioning.

## 18. Rollback
Keep previous artifact/configuration alive until new candidate passes health window when resources permit. On errors/latency regression, route back and record failed transition.

## 19. Post-switch validation
Compare observed performance with predicted. Record residual and realized net gain including migration. Feed local calibration evidence; do not declare success based only on predicted improvement.

## 20. Adaptation log
Each event stores previous/candidate config, observed workload hash, predicted current/candidate costs, uncertainty, migration estimate, horizon, decision, policy, benchmark evidence, actual post-switch metrics and rollback if any.

## 21. Safety margin
Can include fixed cost, percentage, uncertainty margin and operational risk. Version policy. Do not tune after seeing test results without reporting.

## 22. Memory safety
Peak memory during migration is a hard constraint distinct from steady-state candidate memory. If current+candidate exceeds budget, choose offline rebuild or reject transition.

## 23. Build latency
Candidate may be superior steady-state but take too long to build for short-lived workload phase. Transition-aware objective must capture this.

## 24. Adaptation objective
Dynamic research objective:
`min_{C_1..C_T} Σ_t J(C_t,W_t,H) + Σ_{t>1} S(C_{t-1},C_t)`.
Experiments report cumulative cost, not just final-phase latency.

## 25. Predictive adaptation future
If phases are periodic/predictable, prebuild before transition. This “algorithmic time machine” idea must be tested against reactive baseline and prediction errors.

## 26. Drift vs model error
Observed latency worsening may be workload drift, hardware contention or cost-model error. Telemetry should separate operation-mix change from residual change before triggering structural adaptation.

## 27. Machine drift
CPU frequency/host/container changes can invalidate model. Detect machine-profile mismatch and recalibrate rather than incorrectly blaming workload.

## 28. Runtime overhead
Monitoring must be sampled/low overhead. Benchmark application with telemetry off/on. Set overhead budget and report.

## 29. Privacy
Runtime traces can contain keys/user data. Default telemetry stores aggregates/hashes/buckets, not raw sensitive values. Trace export is explicit and access-controlled in SaaS.

## 30. State machine
`STABLE → SUSPECTED_DRIFT → CONFIRMED_DRIFT → REOPTIMIZING → VALIDATING → READY_TO_SWITCH → MIGRATING → VERIFYING → STABLE`; failures → `ROLLBACK/DEGRADED`. Persist transitions for crash recovery.

## 31. Job isolation
Reoptimization/build occurs asynchronously so request path does not block. Runtime service communicates with orchestrator via bounded control channel.

## 32. APIs
`telemetry_snapshot`, `evaluate_drift`, `request_reoptimization`, `estimate_migration`, `evaluate_transition`, `execute_transition`, `rollback`, `adaptation_history`.

## 33. UI
Timeline showing actual workload mix, detected drift, current/candidate predicted+measured metrics, transition-cost equation, decision and realized gain. This is far more credible than an unexplained “AI optimized!” badge.

## 34. Synthetic phase benchmark
Example: phase 1 80% exact/20% range; phase 2 20% exact/80% range; phase 3 return. Compare static config, always-reoptimize/no-hysteresis, MORPHEUS hysteresis. Measure cumulative runtime+migration, switches and SLA violations.

## 35. Adversarial oscillation
Alternate workload just around decision boundary. MORPHEUS should stay stable and outperform naive switch-every-window due to transition cost.

## 36. Short phase
Create workload shift too short to amortize migration. Correct decision is STAY despite candidate lower steady-state latency.

## 37. Long phase
Same shift persists long enough. Correct decision becomes SWITCH.

## 38. Uncertain phase
Predictions overlap/low confidence. Correct action may be BENCHMARK_MORE.

## 39. Failure injection
Candidate build fails; correctness validation fails; cutover health fails; memory insufficient; telemetry missing; orchestrator restarts mid-migration. Test safe state and rollback/recovery.

## 40. Research metrics
Cumulative dynamic cost; adaptation regret vs clairvoyant oracle; switch count; unnecessary-switch rate; missed-beneficial-switch rate; detection delay; migration prediction error; post-switch prediction error; monitoring overhead; rollback success.

## 41. Clairvoyant oracle
Offline dynamic-programming oracle can know complete future phase sequence for small experiment and minimize runtime+migration cost. Compare online MORPHEUS regret against it; label oracle as unattainable upper benchmark.

## 42. Baselines
Static initial optimum; static global optimum; naive threshold; no-hysteresis reoptimize; periodic reoptimize; clairvoyant oracle. Equal candidate space/cost evidence.

## 43. Adaptation policy version
Every decision records `policy_version`, thresholds, lambda, margin, horizon method and drift detector version.

## 44. Runtime artifact compatibility
Stable facade/ABI or process-level routing must allow switching. MVP can run generated services behind proxy and switch target process after validation, which is simpler/safer than in-process hot patching.

## 45. Agentic future
Code rewriting/eBPF/dynamic instrumentation belongs after controlled adaptation works. It must be permissioned and auditable. Do not let autonomous agent modify arbitrary production binaries in MVP.

## 46. Acceptance gates
Immutable declared workload; bounded telemetry; reproducible snapshots; sustained drift detection; explicit migration cost/peak memory; hysteresis/cooldown; STAY/SWITCH/BENCHMARK_MORE; correctness-validated candidate; rollback path; post-switch measurement; complete adaptation log; dynamic benchmark vs baselines; cumulative-cost metric; no false claim of hot swap.

## Build order
Telemetry counters → snapshots → phase workload generator → drift detector → reoptimization trigger → migration estimator → decision policy → offline switch → adaptation log/UI → post-switch validation → shadow build/cutover → rollback → uncertainty/benchmark-more → predictive adaptation.

## North star
A self-designing system is not one that changes often. It is one that knows when changing is worth the cost. MORPHEUS should prefer stability when evidence is weak or phases are short, and adapt only when measured/predicted long-horizon gain justifies migration risk.

**NEXT: MASTER PROMPT #13 — VOLUME 11: BACKEND ORCHESTRATOR, JOB SYSTEM, DATABASE, API, SECURITY & MULTI-TENANT CONTROL PLANE.**
