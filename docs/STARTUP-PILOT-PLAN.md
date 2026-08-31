# MORPHEUS Startup / Integration Pilot Plan

Status: productization plan; no customer traction or external production validation is implied.

## Pilot objective
Prove that MORPHEUS can improve the engineering loop for one bounded workload without requiring a customer to trust an opaque recommendation. A successful pilot must produce an auditable chain from workload definition to generated configuration, verification, measured comparison and rollback/deployment decision.

The repository now includes a separate single-node startup-pilot hardening track: fail-closed preflight, bounded operational telemetry, durable idempotent pilot synthesis, explicit browser policy, manual evidence-audited ambiguity resolution, and content-hashed backup with isolated restore verification. These controls make a bounded pilot safer to operate; they do not convert the local control plane into an HA/multi-tenant production service.

For exact operator procedures, use `docs/STARTUP-PILOT-RUNBOOK.md`.

## Ideal first pilot
Choose a read-heavy service or local analytics component with:
- 1–10 million records or a reproducible subset;
- at least two materially different access patterns;
- a clear baseline implementation;
- a test/staging environment;
- a measurable latency/memory/build objective;
- no requirement for MORPHEUS to own the source-of-truth database.

Avoid an initial pilot where correctness depends on distributed transactions, unbounded graph semantics, native cross-process hot swap or hard real-time guarantees.

## Four-stage pilot

### Stage 0 — discovery and freeze
Deliverables:
- workload inventory;
- schema/cardinality/selectivity snapshot;
- baseline source/version;
- machine profile;
- hard constraints and success metric;
- frozen experiment manifest;
- exact MORPHEUS source commit and pilot capability fingerprint.

Exit gate: customer/engineering owner agrees that the benchmark represents the target problem and MORPHEUS preflight reports no required local blockers.

### Stage 1 — offline synthesis
MORPHEUS runs capability filtering, model/search, generates candidate artifacts and records a decision certificate. No production deployment occurs.

Exit gate: generated candidate passes compile + stateful differential verification for supported routes.

### Stage 2 — shadow measurement
Run baseline and MORPHEUS artifact on identical replay/input. Preserve raw samples and machine/toolchain provenance. Statistical summary is generated from paired measurements.

Exit gate: evidence bundle satisfies the declared measured-performance claim gate, or the result is recorded as negative.

### Stage 3 — guarded integration
If a supported runtime adapter is available, deploy behind feature flag/versioned routing in staging, observe telemetry, and exercise rollback. Native cross-process production hot swap remains prohibited unless separately implemented and verified for the target integration.

Exit gate: explicit owner approval based on evidence, not model prediction alone.

## Pilot success metrics
Primary product metrics:
- time from workload description to verified candidate;
- number of manual design iterations avoided;
- measured objective change vs baseline;
- verification failure rate caught before benchmark/deploy;
- reproducibility rate from frozen manifest;
- rollback time and evidence completeness;
- percentage of idempotent retries resolved without duplicate persisted runs;
- successful verification of at least one recovery checkpoint for the pilot state.

Secondary metrics:
- usability of the MWS specification and Command Center;
- clarity of Copilot explanations;
- percentage of recommendations accepted by engineers;
- engineering time spent integrating generated artifacts.

## Packaging options
1. **Local developer edition** — FastAPI + React + local C++ toolchain + SQLite/content store.
2. **CI optimizer** — workload/benchmark manifests checked into a repo; MORPHEUS generates and verifies candidate artifacts during controlled jobs.
3. **Private control plane** — centralized metadata/evidence service with isolated build workers and customer-owned benchmark runners; this requires storage/identity/isolation work beyond the current single-node pilot implementation.
4. **SDK/library mode** — typed APIs around workload specs, search and artifact manifests.

## Commercial boundaries
Do not sell “automatic guaranteed fastest data structure.” Sell an evidence-backed engineering workflow:
- constrained synthesis;
- reproducible alternatives;
- generated code;
- verification;
- measured comparison;
- provenance;
- controlled adaptation.

The startup-pilot capability ledger explicitly keeps `production_deployment_authorized` false. Pilot readiness is an operational preflight, not a security certification, SLA attestation or customer-success claim.

## Remaining enterprise blockers before a production offering
The following remain outside the current single-node pilot scope:
- isolated/hardened build and benchmark workers beyond bounded host-process execution;
- robust external authn/authz, tenancy and secret-rotation architecture;
- PostgreSQL/object-store or equivalent HA production storage adapters;
- distributed quotas, cancellation and abuse controls;
- signed release/artifact provenance backed by an organizational signing/key-management process;
- **off-host backup retention, scheduled restore drills, disaster-recovery objectives and HA failover** (the current implementation provides content-hashed single-node checkpoints and isolated restore verification only);
- SBOM/dependency/license reporting tied to release policy;
- stronger long-running concurrency/fuzz/chaos validation for target deployment shapes;
- externally governed versioned API compatibility/deprecation policy;
- a real target-specific deployment adapter and native cross-process hot-swap/rollback evidence where that capability is required;
- external security/regulatory review where demanded by the deployment domain.

## Customer-discovery questions
1. Which data-access bottleneck currently requires the most manual tuning?
2. How often does the workload or hardware invalidate a hand-tuned choice?
3. Which evidence is required before a generated component can be deployed?
4. Are memory, tail latency, throughput, build time or update cost the dominant constraints?
5. What is the strongest existing baseline and how is it measured?
6. Can production traffic be replayed or synthesized safely in staging?
7. What rollback/feature-flag mechanism already exists?
8. Which generated-code languages/runtimes are acceptable?
9. Which recovery-point and restore-time objectives would a real production service require?
10. Which identity, tenancy and audit controls are mandatory before customer data can enter the control plane?

## Pilot truth rule
A pilot case study may state only what its claim-gated release manifest supports. A successful local benchmark is not generalized to all workloads, machines or competitors. A successful single-node pilot does not itself establish HA production readiness, universal performance superiority, novelty, patentability or customer traction.
