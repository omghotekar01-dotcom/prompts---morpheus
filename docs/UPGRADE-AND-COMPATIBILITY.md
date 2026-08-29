# MORPHEUS Upgrade & Compatibility Contract

Status: ACTIVE ENGINEERING POLICY  
Applies to: MWS, WorkloadIR, ConfigurationIR, APIs, feature maturity, calibration, generated artifacts, runtime adaptation, evidence and research packages.

## Goal

MORPHEUS must be easy to extend without making old evidence ambiguous or silently changing the meaning of a previous workload, candidate, benchmark or runtime decision. “Updatable” therefore means **versioned evolution with explicit migration and rollback**, not “always accept the newest code.”

A future instruction may add capability, but it may not rewrite historical truth.

## Compatibility hierarchy

The following identities are independent and must remain distinguishable:

1. **Source revision** — Git commit identifying implementation source.
2. **MWS version** — user-facing workload language semantics.
3. **WorkloadIR version/hash** — canonical compiler meaning after validation/default resolution.
4. **Primitive implementation identity** — exact physical implementation calibrated/generated.
5. **ConfigurationIR hash** — canonical selected physical design.
6. **Artifact/evidence schema version** — interpretation contract for persisted JSON/Markdown evidence.
7. **Feature registry version** — maturity and promotion policy.
8. **API contract fingerprint** — route/method/operation surface at a server revision.
9. **Machine/calibration identity** — target-machine evidence binding.

Two artifacts sharing one identity are not assumed equivalent on the others.

## Change classes

### Patch-compatible change

Examples: documentation corrections, error messages, UI layout, additional optional response fields, internal refactor with identical canonical outputs.

Requirements:

- existing tests stay green;
- canonical semantic hashes remain unchanged for equivalent input;
- no evidence state is upgraded automatically;
- API required routes remain present;
- generated behavior remains differential-test equivalent where applicable.

### Backward-compatible feature addition

Examples: optional MWS field with a fully specified default, new research endpoint, new primitive not selected unless compatible, new optional evidence field.

Requirements:

- explicitly specify default/absence semantics;
- add tests proving old inputs retain prior semantics;
- add capability/feature-registry entry;
- feature maturity begins no higher than evidence supports;
- add provenance so old/new artifacts can be distinguished.

### Semantic/breaking change

Examples: changing meaning of an existing MWS field, changing canonical lowering, changing ConfigurationIR identity rules, changing required evidence fields, removing/renaming a route, replacing physical primitive semantics.

Requirements:

- increment the relevant schema/IR/protocol version;
- retain a reader/migration path where practical;
- never reuse an old semantic hash/version for new meaning;
- update release notes and compatibility tests;
- require a deliberate feature-registry revision;
- re-run affected calibration/research rather than carrying old measurements forward.

## Feature maturity

`backend/app/feature_registry.py` is the machine-readable feature policy.

Maturity meanings:

- `stable` — normal supported engineering surface. This is not a performance or publication claim.
- `guarded` — implemented and usable only behind explicit correctness/evidence/runtime gates.
- `research` — implemented for study; cannot influence automatic runtime control.
- `blocked` — unavailable for activation even if partial code exists.

Research/blocked features cannot set `automatic_control_allowed=true`. Dependencies must exist and be non-blocked, but non-decision infrastructure does not acquire control authority merely because a control feature depends on it.

## Safe promotion rule

Moving a feature upward in maturity is a reviewed code change, not a runtime toggle. Promotion must include:

1. named evidence supporting the new maturity;
2. failure/negative-result analysis;
3. tests for new invariants;
4. rollback or fail-closed behavior;
5. updated truth boundary;
6. updated registry version if the policy contract changes;
7. full CI before merging;
8. controlled research rerun when scientific conclusions could change.

Synthetic evidence alone cannot promote an inference system to autonomous control.

## API evolution

`GET /api/v2/system/schema-contract` exposes a deterministic route-level OpenAPI fingerprint. It is designed to flag accidental surface drift, not to prove full JSON-field semantic compatibility.

Rules:

- additive optional response fields are preferred;
- required request-field changes require explicit versioning;
- do not remove a mature route without a migration window;
- operation IDs must remain unique;
- new incompatible surfaces go under a new versioned namespace;
- clients must not infer performance/evidence meaning from HTTP success alone.

For critical payloads, Pydantic/schema tests remain the source of field-level contract enforcement.

## Evidence and calibration compatibility

Measurements are reusable only when all required provenance matches the consuming decision. Depending on the measurement class this includes workload semantic hash, WorkloadIR hash, ConfigurationIR hash, primitive implementation ID, record count, access distribution, machine/toolchain identity and protocol version.

Never:

- relabel an old physical implementation with a new primitive identity;
- apply a uniform calibration to a skewed workload without an explicitly validated model;
- extrapolate outside a measured calibration range merely to avoid `unknown`;
- promote GitHub-hosted exploratory timings to publication evidence;
- rewrite an evidence-state string to make evidence appear stronger.

When evidence is incompatible, MORPHEUS must fall back to a weaker evidence state or refuse the inference.

## Runtime update safety

A runtime candidate change requires the current guarded migration protocol. In-process coordination checks:

- pending candidate still matches migration target;
- active runtime candidate still matches migration source;
- shadow artifact and verification identity exist;
- compile/correctness verification succeeded;
- local data-plane staged candidate matches target;
- commit failures trigger compensation of already-mutated local controllers;
- rollback preconditions are checked before mutation;
- stale readers retain snapshot/reference semantics.

This does **not** imply a distributed ACID transaction or native cross-process hot swap.

## UI/startup update safety

The startup overlay performs real read-only readiness checks and has bounded waits. It may enter degraded mode, but must not fabricate successful initialization. The root React error boundary may retry/reload the interface but may not mutate engine/runtime state as a side effect of rendering recovery.

The MORPHEUS logo is a visual identity asset; changing presentation must not change engine semantics or evidence state.

## Required workflow for a new instruction

When a new instruction requests a feature:

1. inspect current source-of-truth and CI;
2. classify change as patch/additive/breaking;
3. identify affected contracts and evidence;
4. implement the smallest coherent vertical slice;
5. add correctness and failure-path tests;
6. register feature/maturity when it creates a new capability;
7. run relevant local/CI gates;
8. fix regressions before promotion;
9. update docs/changelog only with verified facts;
10. retain explicit limitations and next evidence needed.

No user instruction should be interpreted as permission to falsify evidence, disable safety gates, hide test failures or call an unvalidated feature “production-ready.”

## Backout strategy

Every meaningful upgrade should be revertable at the source revision level. Runtime changes additionally require an application-level rollback path where state changes are involved. If a migration cannot be safely reversed, MORPHEUS must block automatic promotion until that limitation is explicitly accepted by the relevant deployment policy.

## Compatibility checklist

Before declaring an upgrade integrated:

- [ ] Full CI is green on the exact head commit.
- [ ] Existing MWS examples still validate or have a documented migration.
- [ ] Canonical IR/hash tests cover semantic identity.
- [ ] Feature registry validates with no cycles/unsafe promotion.
- [ ] API operation IDs are unique and critical routes remain present.
- [ ] Evidence/calibration provenance cannot cross incompatible identities.
- [ ] Runtime state-changing paths have fail-closed preconditions and rollback/compensation tests.
- [ ] Frontend production build passes.
- [ ] Research-only features remain excluded from automatic control.
- [ ] Documentation states what is implemented, measured, unverified and blocked.

That checklist is an engineering gate, not a claim that all future bugs are impossible.
