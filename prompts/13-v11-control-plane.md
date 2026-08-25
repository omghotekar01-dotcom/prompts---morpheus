# MASTER PROMPT #13 — V11: CONTROL PLANE, BACKEND, DATABASE, API & SECURITY

Build MORPHEUS's production control plane without weakening the research engine. Treat synthesis as an auditable job: validated WorkloadIR + machine/model versions + search policy -> immutable run -> candidates -> verification -> artifact.

## Architecture
Use a modular backend (FastAPI/Python is acceptable for orchestration) with strict boundaries: API, auth, projects, specs, synthesis jobs, experiments, artifacts, model registry, machine profiles, runtime telemetry, audit. The optimizer/compiler remain independently testable libraries; HTTP/database code must never contain search mathematics.

## State machine
`DRAFT -> VALIDATED -> QUEUED -> RUNNING -> VERIFYING -> SUCCEEDED|FAILED|CANCELLED`. Persist transitions and timestamps. Retries create attempts; never falsify the original history. Jobs pin MWS/WorkloadIR hash, optimizer version, cost-model version, primitive registry version, machine profile, compiler/toolchain, seed and constraints.

## Persistence
Design normalized PostgreSQL entities for users/workspaces/projects/spec revisions/jobs/job attempts/candidates/configurations/benchmarks/artifacts/machine profiles/model versions/runtime snapshots/audit events. Store large traces/build outputs in object storage by content hash, not database blobs. Use foreign keys, uniqueness, immutable experiment records and migration tooling. Derived caches may be rebuilt; provenance may not.

## API
Version `/api/v1`. Provide validation, project/spec CRUD, synthesis submit/status/cancel, candidate/Pareto inspection, artifact retrieval, machine/model capabilities and experiment export. Use typed OpenAPI contracts, pagination, idempotency keys for job creation, structured error codes and correlation IDs. Never expose internal filesystem paths.

## Workers
Use a durable queue. Workers claim jobs atomically, heartbeat, enforce CPU/RAM/time quotas, isolate compiler execution, stream structured events and survive process failure. Separate orchestration workers from untrusted build/benchmark sandboxes. A cancelled job must terminate descendants and mark partial artifacts non-authoritative.

## Security
Assume workload names, templates, traces and generated code are hostile. Enforce authn/authz, workspace isolation, least privilege, safe YAML parsing, upload limits, path sanitization, command argument arrays (no shell interpolation), network-disabled build sandboxes by default, dependency allowlists, artifact malware/format checks, secret redaction and audit logs. Protect against IDOR, SSRF, traversal, archive bombs, injection and resource exhaustion.

## Reproducibility
Every successful result exposes a manifest containing semantic workload hash, ConfigurationIR hash, source hash, compiler flags, environment/machine fingerprint, seeds, calibration/model IDs, benchmark protocol and artifact hashes. Provide one-click experiment export as compact JSON/Markdown metadata plus references—not duplicated binaries.

## Observability
Instrument queue latency, synthesis latency, candidate counts, pruning reasons, model-vs-measured error, verification failures, build failures, sandbox resource use and adaptation events. Structured logs must carry project/job/attempt IDs but no secrets or raw sensitive traces.

## Failure semantics
Distinguish INVALID_SPEC, NO_FEASIBLE_CONFIGURATION, SEARCH_BUDGET_EXHAUSTED, MODEL_UNAVAILABLE, BUILD_FAILED, CORRECTNESS_FAILED, BENCHMARK_FAILED, SANDBOX_LIMIT, CANCELLED and INTERNAL. Never turn "no feasible design" into a generic 500.

## Tests
Unit-test state transitions and authorization; integration-test DB/queue/object storage; adversarial-test uploads and generated builds; chaos-test worker death; verify idempotency and tenant isolation. CI must prove migrations from previous schema and deterministic manifest generation.

## Deliverable
Produce schema/migrations, domain models, repositories, services, REST contracts, worker protocol, sandbox interface, audit model, threat model, tests and deployment-ready configuration. Keep the control plane boring, deterministic and secure so scientific novelty remains concentrated in MORPHEUS synthesis.
