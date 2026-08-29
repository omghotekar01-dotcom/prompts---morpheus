# RQ7 — Generated-Configuration Migration Cost and Reader Safety

Status: **FROZEN DESIGN + EXECUTION + CONFIRMATORY-ANALYSIS TOOLING IMPLEMENTED; full controlled local campaign not yet accepted as measured evidence**

Truth rule: this protocol, its frozen matrix, CI smoke runs, unit-test fixtures and generated example numbers are **not** publication measurements. A measured RQ7 claim requires the complete-local evidence chain defined below. The implemented H7 analysis is an analysis protocol, not a substitute for real non-CI measurements.

## 1. Research question

When MORPHEUS changes from one synthesized physical configuration to a distinct synthesized physical configuration for the same WorkloadIR, how does the full same-process transition cost behave as logical state size and concurrent immutable-reader pressure increase, and can the transition complete without exposing an invalid published generation?

The transition measured here is intentionally larger than a pointer swap. The primary path includes logical snapshot/reconstruction work performed by the generated source/target types, target shadow validation, type-erased validated publication and the associated transition protocol. Rollback is measured separately.

## 2. Hypothesis

**H7.** For the frozen generated-candidate pair policy and workload, same-process migration cost will change systematically with logical record count while the publication protocol preserves zero invalid immutable-reader observations across the declared reader-pressure matrix.

H7 is deliberately not phrased as a universal complexity or superiority claim. A single-machine campaign can characterize the frozen scope; it cannot establish cross-machine or production generalization.

## 3. Frozen matrix

Canonical matrix: `research/matrices/rq7-generated-migration.json`.

The v1 matrix expands to **24 factor configurations**, each with **10 repetitions**:

| Factor | Frozen values |
|---|---|
| workload | `users_demo` |
| candidate-pair policy | winner → best distinct feasible candidate |
| logical record count | 128, 1,024, 8,192, 65,536 |
| concurrent immutable readers | 1, 4, 16 |
| transitions per repetition | 10, 100 |
| repetitions | 10 |
| seed identity | 0 |

Seed `0` is a protocol identity, not randomized sampling. The v1 harness uses deterministic schema-derived records. A future randomized-value protocol must use a new protocol/schema version rather than silently reinterpreting the seed.

## 4. Candidate identity

The campaign synthesizes once from the declared WorkloadSpec and chooses the deterministic `winner-to-best-distinct` pair. The source and target must:

- be feasible;
- have different candidate IDs;
- share the same WorkloadIR hash;
- have different ConfigurationIR hashes;
- have separately content-hashed generated C++ headers and artifact provenance manifests.

The candidate pair is fixed for the campaign. Changing the pair is a new campaign identity, not an additional repetition.

## 5. Primary and secondary measurements

Primary metric:

- `migrate_validate_activate_ns_per` — average wall-clock nanoseconds per requested Source→Target transition, including generated logical migration/rebuild, target validation and validated publication.

Secondary metrics:

- `rollback_ns_per`;
- round-trip transition cost = migration + rollback;
- concurrent reader observations;
- invalid reader observations;
- compile/run status and exact compiler identity.

Every accepted benchmark report must have `invalid_reads == 0` for every repetition. Any non-zero value fails the evidence contract; it is not an outlier to remove.

## 6. Machine, toolchain and measurement-environment provenance

A campaign is bound to one `morpheus-machine-profile-v2` identity. The stable machine fingerprint includes platform, CPU metadata and the same compiler selected by MORPHEUS `discover_toolchain()`, including `MORPHEUS_CXX` overrides.

The campaign rejects a successful benchmark report if compiler executable, compiler kind or compiler version differs from the captured machine profile.

The runner also emits a content-hashed `measurement_environment_record` when an invocation actually measures new cells. Its start/end snapshots record observable metadata when available, including:

- process CPU affinity;
- logical CPU count;
- Linux scaling governors and observed frequency summary;
- Windows active power scheme;
- load averages;
- thermal sensor summary;
- GitHub Actions identity.

The record validates timestamp ordering, nested snapshot hashes, normalized-load consistency, affinity structure, frequency/thermal structure, experiment coverage and recomputed stability flags. It is still **observational provenance, not laboratory-control proof**: it cannot prove exclusive machine access, constant frequency between snapshots, interrupt absence, cache state, NUMA placement or thermal equilibrium.

For the strongest H7 record-count-effect claim, the packaged environment record must cover all 24 analyzed cells in **one fresh non-CI invocation**, match the packaged machine profile, expose stable process affinity, and expose a stable CPU governor or Windows power scheme. A resumed multi-invocation campaign can remain valid measurement evidence, but one later environment record cannot be used to pretend it covered reused cells.

## 7. Evidence states

The benchmark distinguishes at least these states:

- `MEASURED_CI_SMOKE_GENERATED_MIGRATION_TRANSITION_COST`
- `MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST`

Campaign aggregation distinguishes partial, failed, CI-only, homogeneous local and mixed-environment states. CI measurements remain smoke evidence even if every frozen factor happens to execute successfully.

Environment provenance distinguishes local metadata from CI metadata; a CI environment record cannot upgrade CI timings into publication measurements.

## 8. Complete-local transition-cost attestation

The role `generated_migration_transition_cost_evidence` may be minted only when all of the following are true:

1. all 24 frozen RQ7 experiments executed;
2. every experiment succeeded;
3. every report is `MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST`;
4. the campaign is homogeneous/comparable by its declared environment contract;
5. every repetition reports zero invalid reader observations;
6. the descriptive summary covers every experiment;
7. campaign, summary, experiment manifest, machine profile and source/target identities cross-link by hashes.

A partial campaign, mixed-environment campaign or GitHub Actions campaign is categorically ineligible for this attestation.

## 9. Release claim gates

### 9.1 Measured transition cost

The public claim type `generated_migration_transition_cost_measured` requires:

- `experiment_manifest`;
- `generated_migration_campaign`;
- `generated_migration_campaign_summary`;
- `generated_migration_transition_cost_evidence`;
- `machine_profile`.

This supports only the narrow statement that same-process generated-migration transition costs were measured over the complete frozen RQ7 matrix on the declared machine/toolchain.

### 9.2 H7 systematic record-count effect

The narrower inferential claim type `rq7_systematic_record_count_effect` additionally requires:

- `rq7_confirmatory_analysis`;
- `measurement_environment_record` with complete single-invocation coverage and matching machine identity.

The release package cross-linker checks analysis↔campaign↔manifest↔machine↔transition-attestation↔environment identities and verifies the H7 environment-coverage/stability semantics.

Neither claim authorizes statements that:

- an asymptotic complexity law has been established;
- MORPHEUS migration is faster than another system;
- results generalize to another machine/compiler;
- concurrent writers are safely migrated;
- native cross-process/distributed hot replacement works;
- production availability/SLA targets are met.

## 10. Implemented H7-v1 confirmatory analysis

Canonical implementation: `backend/app/rq7_confirmatory_analysis.py`.

Schema: `morpheus-rq7-confirmatory-analysis-v1`.

The analysis accepts only a complete comparable non-CI local RQ7 campaign with all 24 frozen cells, exactly 10 repetitions per cell and zero invalid-reader observations.

### 10.1 Analysis unit

Raw timing repetitions remain exposed, but they are **not treated as 240 independent workloads**. The primary analysis first reduces each factor cell to its median and then uses matched factor blocks as the resampling/inference unit.

### 10.2 Record-count effect

For each of the 3 reader levels × 2 transition-count settings, H7-v1 forms one four-scale record-count block, giving **6 matched blocks**. Within each block it fits the slope of `log(cell median cost)` against record-size doublings. It reports:

- six block slopes and multiplicative cost ratios per record doubling;
- mean/median block slope;
- geometric mean ratio per doubling;
- deterministic 10,000-round bootstrap CI over the six block slopes, seed `7007`;
- exact two-sided sign test over block slopes.

The v1 record-count effect is marked `SUPPORTED` only when the exact sign-test p-value is ≤ 0.05 **and** the bootstrap lower bound for the mean log-slope is positive. This is a frozen-scope systematic-effect decision, not a universal scaling-law claim.

### 10.3 Reader-pressure sensitivity

Reader-pressure sensitivity is evaluated separately through `readers_4_vs_1` and `readers_16_vs_1`. Each contrast uses **8 matched record×transition blocks**. H7-v1 reports geometric ratios, deterministic bootstrap uncertainty and exact sign tests. The two confirmatory reader contrasts form one family corrected with the repository's Holm-Bonferroni step-down implementation.

### 10.4 Transition-count robustness

`transitions_100_vs_10` uses **12 matched record×reader blocks**. It is treated as a measurement-duration/robustness contrast, not silently pooled with the primary record-size effect. A non-significant result is not interpreted as equivalence or proof of no effect.

### 10.5 Descriptive global model

A 24-cell additive OLS model on log cell-median cost reports effect-size coefficients, residuals, RMSE and R². Its declared role is **descriptive residual/effect-size modeling only**; it does not manufacture confirmatory p-values from unverified OLS assumptions.

### 10.6 Analysis evidence

`rq7_confirmatory_analysis` is content hashed and structurally validated for factor coverage, repetition counts, matched-block counts, bootstrap protocol, Holm family, residual model, reader-safety invariant and top-level H7 decision consistency.

The offline command:

`python scripts/analyze_rq7_generated_migration.py <generated-migration-campaign.json> --output <rq7-confirmatory-analysis.json>`

loads and strictly validates persisted campaign evidence before reconstructing typed objects. It does not compile C++ or rerun timing measurements.

## 11. Execution, checkpointing and resume

Canonical measurement runner:

`python scripts/run_generated_migration_campaign.py examples/users-demo.yaml --output-dir <dir>`

The runner emits, as applicable:

- `generated-migration-experiment-manifest.json`;
- `generated-migration-machine-profile.json`;
- `generated-migration-campaign.json`;
- `generated-migration-summary.json`;
- `generated-migration-measurement-environment.json` when new cells were measured;
- `generated-migration-transition-cost-evidence.json` only when complete-local eligibility is satisfied;
- `generated-migration-checkpoint.json` for an incomplete campaign.

Every accepted cell can be atomically checkpointed. `--resume-from <campaign-or-checkpoint.json>` reuses only prior successful cells whose frozen matrix, generated-candidate identity, machine fingerprint, compiler identity, factor hash, report hash, campaign hash and reader-safety evidence all validate. Failed prior cells are never silently replaced through resume. If every requested cell is already verified, the campaign path performs zero new benchmark executions.

Resume is useful for engineering recovery and measured-cost preservation, but a resumed multi-invocation run cannot satisfy the strongest H7 single-invocation environment-coverage requirement.

`--limit N` is an engineering/smoke control. Partial campaigns cannot mint complete-local attestations.

## 12. Failure and negative-result policy

Record and preserve:

- compile or run failures;
- non-zero invalid-reader observations;
- record scales that exceed practical machine capacity;
- cases where migration cost grows too quickly to repay adaptation benefit;
- unexpected reader-pressure sensitivity;
- toolchain-specific anomalies;
- mixed-environment or provenance mismatches;
- unstable or unavailable measurement-environment controls.

Do not silently retry until a favorable timing appears. A failed factor configuration is evidence about the campaign and must remain visible.

## 13. Current boundary

Implemented and tested infrastructure includes:

- generated source/target migration benchmark and strict benchmark evidence verifier;
- frozen 24×10 RQ7 matrix;
- compile-once campaign execution;
- hash-verified atomic checkpoint/resume semantics;
- machine/toolchain binding;
- descriptive campaign summary;
- complete-local transition-cost attestation;
- measurement-environment snapshots/coverage records;
- H7-v1 matched-block confirmatory analysis and offline analysis CLI;
- strict release structural validation, cross-artifact validation and narrow claim gates.

Still required for scientific closure:

1. execute and preserve one fresh controlled non-CI 24-cell × 10-repetition campaign on a declared measurement machine with zero invalid reads and full single-invocation environment coverage;
2. run H7-v1 offline on that real campaign and package the complete evidence chain;
3. report negative/ambiguous H7 outcomes exactly as produced rather than tuning the protocol after seeing results;
4. replicate on additional declared hardware/toolchains before making external-validity or cross-machine claims.

No current repository fixture or CI run satisfies item 1. Therefore no real H7 effect size, scaling statement or publication-grade transition-cost number is asserted by this document.
