# RQ7 — Generated-Configuration Migration Cost and Reader Safety

Status: **FROZEN DESIGN + EXECUTION TOOLING IMPLEMENTED; full controlled local campaign not yet accepted as measured evidence**

Truth rule: this protocol, its frozen matrix, CI smoke runs, unit-test fixtures and generated example numbers are **not** publication measurements. A measured RQ7 claim requires the complete-local evidence chain defined below.

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

## 6. Machine and toolchain provenance

A campaign is bound to one `morpheus-machine-profile-v2` identity. The stable machine fingerprint includes platform, CPU metadata and the same compiler selected by MORPHEUS `discover_toolchain()`, including `MORPHEUS_CXX` overrides.

The campaign rejects a successful benchmark report if compiler executable, compiler kind or compiler version differs from the captured machine profile.

The machine profile does **not** currently prove controlled CPU frequency, governor/power-plan state, cache topology, thermals, NUMA placement, process affinity or background load. Those controls must be recorded separately before final paper-grade execution.

## 7. Evidence states

The benchmark distinguishes at least these states:

- `MEASURED_CI_SMOKE_GENERATED_MIGRATION_TRANSITION_COST`
- `MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST`

Campaign aggregation distinguishes partial, failed, CI-only, homogeneous local and mixed-environment states. CI measurements remain smoke evidence even if every frozen factor happens to execute successfully.

## 8. Complete-local attestation

The role `generated_migration_transition_cost_evidence` may be minted only when all of the following are true:

1. all 24 frozen RQ7 experiments executed;
2. every experiment succeeded;
3. every report is `MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST`;
4. the campaign is homogeneous/comparable by its declared environment contract;
5. every repetition reports zero invalid reader observations;
6. the descriptive summary covers every experiment;
7. campaign, summary, experiment manifest, machine profile and source/target identities cross-link by hashes.

A partial campaign, mixed-environment campaign or GitHub Actions campaign is categorically ineligible for this attestation.

## 9. Release claim gate

The public claim type `generated_migration_transition_cost_measured` requires these packaged roles:

- `experiment_manifest`;
- `generated_migration_campaign`;
- `generated_migration_campaign_summary`;
- `generated_migration_transition_cost_evidence`;
- `machine_profile`.

This gate supports only the narrow statement that same-process generated-migration transition costs were measured over the complete frozen RQ7 matrix on the declared machine/toolchain.

It does **not** authorize claims that:

- a particular asymptotic/scaling law has been established;
- MORPHEUS migration is faster than another system;
- results generalize to another machine/compiler;
- concurrent writers are safely migrated;
- native cross-process/distributed hot replacement works;
- production availability/SLA targets are met.

## 10. Statistical analysis policy

The current campaign summary is descriptive: `n`, mean, median, standard deviation, minimum, p95, p99 and maximum per factor cell for migration, rollback and round-trip cost.

A future confirmatory H7 analysis must be versioned separately and should, at minimum:

- model record-count effect without treating repeated timing observations as independent workloads;
- expose cell-level raw repetitions;
- evaluate reader-pressure sensitivity separately from state-size sensitivity;
- treat transition-count variation as a robustness/measurement-duration factor rather than silently pooling it;
- report model residuals and effect sizes;
- bootstrap or otherwise quantify uncertainty under an explicitly justified resampling unit;
- correct any family of confirmatory multiple comparisons using the repository's Holm-Bonferroni implementation;
- keep exploratory model selection separate from a held-out/confirmatory analysis where practical.

Until that analysis exists, RQ7 supports measured-transition-cost claims but not a confirmed scaling-law claim.

## 11. Execution

Canonical runner:

`python scripts/run_generated_migration_campaign.py examples/users-demo.yaml --output-dir <dir>`

The runner emits:

- `generated-migration-experiment-manifest.json`;
- `generated-migration-machine-profile.json`;
- `generated-migration-campaign.json`;
- `generated-migration-summary.json`;
- `generated-migration-transition-cost-evidence.json` **only when complete-local eligibility is satisfied**.

`--limit N` is explicitly a partial run for engineering/smoke use. It cannot mint the complete-local attestation.

## 12. Failure and negative-result policy

Record and preserve:

- compile or run failures;
- non-zero invalid-reader observations;
- record scales that exceed practical machine capacity;
- cases where migration cost grows too quickly to repay adaptation benefit;
- unexpected reader-pressure sensitivity;
- toolchain-specific anomalies;
- mixed-environment or provenance mismatches.

Do not silently retry until a favorable timing appears. A failed factor configuration is evidence about the campaign and must remain visible.

## 13. Current boundary

Implemented and tested infrastructure: generated source/target migration benchmark, strict report verifier, frozen RQ7 matrix, campaign executor, machine-profile binding, descriptive summary, complete-local attestation logic, release structural validation, cross-artifact validation and claim gating.

Still required for scientific closure: execute and preserve a controlled full local campaign on a declared measurement machine; add controlled power/affinity/background-load metadata; implement the versioned confirmatory scaling analysis; replicate on additional hardware/toolchains if making external-validity claims.
