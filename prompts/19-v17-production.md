# MASTER PROMPT #19 — V17: PRODUCTION INFRASTRUCTURE, DEPLOYMENT, RELIABILITY & OBSERVABILITY

Build MORPHEUS so the research prototype can become a dependable deployable system without contaminating scientific reproducibility.

## Environments
Define local/dev/test/staging/production profiles with configuration-as-code. Containers must be reproducible and minimal. Pin toolchains used for scientific experiments. Separate web/control-plane services from privileged compilation/benchmark workers.

## Deployment topology
Components: frontend; API/control plane; PostgreSQL; durable queue; object/artifact storage; synthesis workers; isolated compiler/benchmark runners; telemetry collector. Allow a single-machine developer deployment and horizontally scalable server deployment from the same contracts.

## Isolation
Execute generated code in disposable sandboxes with CPU, memory, process, filesystem and wall-clock limits; deny network by default; mount only required inputs; capture stdout/stderr/exit/resource metrics; destroy sandbox after completion. Never run generated binaries inside API process.

## Reliability
Use idempotent job submission, durable state transitions, leases/heartbeats, bounded retries with classification, graceful shutdown, cancellation propagation and artifact integrity checks. Define recovery for API restart, worker death, queue outage, DB outage and object-store failure.

## Observability
OpenTelemetry-compatible traces/metrics/logs. Measure request latency/errors, queue depth/wait, synthesis duration, candidate throughput, pruning, model error, compilation/verification failure, benchmark noise, sandbox limits, artifact size and runtime adaptation. Correlate via job/attempt IDs.

## SLOs
Define realistic control-plane SLOs separately from research job duration. Never promise synthesis completion latency before empirical capacity tests. Establish error budgets only after measuring workloads.

## Capacity
Benchmark worker CPU/RAM/disk requirements; implement per-tenant concurrency quotas and backpressure. Avoid autoscaling based solely on CPU when queue depth/job class is more meaningful.

## Data protection
Encrypt transport, use managed secret storage, rotate credentials, minimize retained raw traces, define retention/deletion policy and backups. Test restore—not merely backup creation.

## Supply chain
Pin dependencies, produce SBOM, scan dependencies/images, verify artifact hashes, restrict build images and compiler versions, use signed releases when mature. Generated projects receive a manifest describing dependencies and provenance.

## Releases
Semantic versions for engine/API/MWS/IR independently where needed. CI gates lint/type/unit/integration/security/reproducibility tests. Staging runs golden synthesis workloads before promotion. Support rollback of services and model versions.

## Deliverable
Produce Docker/container definitions, local compose stack, production deployment manifests, worker sandbox policy, config schema, secrets strategy, backup/restore runbook, telemetry dashboards, alerts, SLO document, capacity plan, release pipeline and disaster-recovery tests. Production engineering must make MORPHEUS trustworthy, not merely available.
