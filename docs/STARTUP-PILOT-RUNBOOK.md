# MORPHEUS Startup Pilot Operations Runbook

Status: **single-node engineering pilot runbook**. This document does not authorize external production deployment and does not widen MORPHEUS into an HA, multi-tenant or distributed service.

## 1. Operating boundary

The startup pilot uses the existing MORPHEUS control plane with:

- one MORPHEUS application node and exactly one application worker;
- file-backed SQLite metadata and idempotency journals;
- the local content-addressed artifact store;
- one local C++20 verification toolchain;
- API-key protection and process-local rate limiting;
- bounded process-local telemetry;
- explicit idempotency for the versioned pilot synthesis endpoint;
- CLI-only backup/restore and ambiguity-resolution operations.

It does **not** provide distributed exactly-once execution, cross-process native hot swap, HA database/object storage, multi-tenant RBAC, external security certification or a production SLA.

## 2. Startup gate

Before starting a guarded pilot, configure a non-empty control-plane API secret of at least 24 characters, a positive per-minute request limit, file-backed state/journal paths, and an available C++20 compiler. Never commit secrets to the repository.

Run the fail-closed preflight from the repository root:

```bash
python scripts/check_pilot_readiness.py
```

Exit codes:

- `0`: every required local pilot precondition passed;
- `3`: at least one required condition blocks pilot startup;
- `2`: the preflight itself failed and startup must remain blocked.

The machine-readable API equivalent is `GET /api/v2/system/pilot-readiness`. The API intentionally omits raw secret values, configuration-variable names and local filesystem/compiler paths.

Also inspect the scope ledger at `GET /api/v2/system/pilot-capabilities`. `production_deployment_authorized` must remain `false` unless a future, separately reviewed deployment program changes the declared scope.

## 3. Guarded start and request discipline

For a pilot, use the preflight-enforcing launcher rather than invoking Uvicorn directly:

```bash
python scripts/run_pilot.py
```

The launcher:

- builds a deterministic launch plan;
- runs the same fail-closed readiness gate before starting the server;
- refuses startup when any required readiness blocker exists;
- fixes the application worker count at exactly `1` because telemetry/rate limiting are process-local and this is a single-node contract;
- binds to `127.0.0.1:8000` by default;
- rejects a non-loopback bind unless the operator explicitly supplies `--allow-network-bind`;
- keeps `production_deployment_authorized` false even when a network bind is explicitly acknowledged.

For example, a staging host behind separately managed TLS/gateway controls may be started only with an explicit acknowledgement such as:

```bash
python scripts/run_pilot.py --host 0.0.0.0 --port 8000 --allow-network-bind
```

That flag **does not** add TLS, identity, a WAF/gateway, tenancy, distributed rate limiting or production authorization. Those remain external requirements.

The mature application entrypoint remains `app.server:app`; the guarded launcher uses that same entrypoint rather than creating a second application implementation.

For a startup pilot, prefer the versioned synthesis route:

`POST /api/v2/pilot/synthesize`

Every request must carry an `Idempotency-Key` whose value is unique to one logical synthesis request. MORPHEUS persists only the key hash. The contract is:

- same key + same request -> replay the persisted response;
- same key + different request -> conflict;
- active pending request -> fail closed as in progress;
- unresolved ambiguous side effect -> fail closed pending investigation;
- confirmed prior side effect -> the original key stays blocked.

This is a **single-node SQLite-backed idempotency contract**, not a distributed exactly-once transaction.

## 4. Browser boundary

Browser access to pilot routes uses the dedicated explicit-origin policy. Do not replace it with wildcard origins, wildcard headers or credentialed CORS to make integration easier.

CORS is browser interoperability policy, not authentication. The API secret, upstream TLS termination and any future identity/gateway layer remain separate controls.

## 5. Operational observation

Use:

- `GET /api/health` for basic process liveness only;
- `GET /api/v2/system/pilot-readiness` for fail-closed local readiness;
- `GET /api/v2/system/pilot-capabilities` for the scope-qualified startup capability fingerprint;
- `GET /api/v2/system/operational-metrics` for bounded process-local request/latency/status aggregates;
- `GET /api/v2/system/idempotency/status` for aggregate journal state counts;
- `GET /api/v2/system/schema-contract` for the route-contract fingerprint.

The operational metrics intentionally do not capture request bodies, query strings, API keys or authorization material. They reset on process restart and are not an SLA record or distributed tracing system.

A nonzero `AMBIGUOUS_FAILURE` count is an operator incident and blocks pilot readiness. A `PENDING` record is an advisory because it may represent a currently active request; do not infer that it is orphaned from age alone. `RESOLVED_SIDE_EFFECT_PRESENT` preserves a confirmed incident for the original key without counting it as unresolved ambiguity.

## 6. Ambiguous idempotency incident procedure

No MORPHEUS command automatically retries or clears an ambiguous request.

List unresolved records locally:

```bash
python scripts/resolve_pilot_idempotency.py list
```

Investigate the actual persisted side effect using the MORPHEUS run/evidence store and the target integration. Prepare a UTF-8 incident rationale file locally. Only its SHA-256 is persisted by the resolution workflow.

If investigation proves that **no side effect occurred**:

```bash
python scripts/resolve_pilot_idempotency.py resolve \
  --operation <operation> \
  --key-sha256 <key-sha256> \
  --request-sha256 <request-sha256> \
  --outcome CONFIRMED_NO_SIDE_EFFECT \
  --operator <operator-id> \
  --reason-file <incident-rationale.txt>
```

The reservation may then be removed by the audited resolution workflow. Any retry remains a new **explicit operator/client action**; MORPHEUS does not trigger it automatically.

If investigation proves that the side effect **did occur**:

```bash
python scripts/resolve_pilot_idempotency.py resolve \
  --operation <operation> \
  --key-sha256 <key-sha256> \
  --request-sha256 <request-sha256> \
  --outcome CONFIRMED_SIDE_EFFECT_PRESENT \
  --operator <operator-id> \
  --reason-file <incident-rationale.txt>
```

The original key then remains permanently blocked rather than manufacturing a replay response. Resolution authorization/application evidence is appended to the hash-chained evidence ledger.

The newer retry authorization, fence, history, ledger, seal and freshness modules provide deterministic **offline evidence validation** for a retry lineage. They do not themselves grant automatic live retry authority.

## 7. Recovery checkpoint

Create a recovery checkpoint only when the idempotency journal has **zero pending and zero unresolved ambiguous operations**:

```bash
python scripts/manage_pilot_backup.py create <new-backup-directory>
```

The backup process serializes access to the MORPHEUS state and idempotency journals, snapshots both SQLite databases, copies the content-addressed artifacts referenced by the state snapshot, and writes a hash-bound manifest.

Verify a checkpoint before relying on it:

```bash
python scripts/manage_pilot_backup.py verify <backup-directory>
```

Restore only into a new isolated directory:

```bash
python scripts/manage_pilot_backup.py restore <backup-directory> <new-restore-directory>
```

Restore never overwrites the active state. The restored SQLite stores, evidence chain and artifact identities are verified before the isolated target is accepted. Switching a future MORPHEUS process to that restored state is a separate operator decision.

This is a local recovery checkpoint, **not** continuous replication, off-site retention, disaster recovery across regions, or HA failover.

## 8. Pilot stop conditions

Stop or keep the pilot blocked when any of these occur:

- pilot preflight returns a blocker;
- the evidence ledger fails integrity verification;
- the idempotency journal fails SQLite/integrity checks;
- unresolved ambiguous side effects exist;
- generated artifacts fail compile or behavioral correctness gates;
- the target workload requires unsupported semantics;
- a deployment would require native cross-process hot swap, distributed transactions, HA or hard real-time guarantees that MORPHEUS does not implement;
- a measured claim cannot be reproduced under the frozen benchmark/evidence protocol.

Do not bypass a blocker by relabeling model predictions, CI smoke timings or local evidence as production proof.

## 9. Pilot completion package

A defensible pilot package should preserve:

1. the workload specification and canonical WorkloadIR identity;
2. decision/configuration/artifact identities;
3. compile and correctness verification evidence;
4. benchmark protocol, raw samples and machine/toolchain provenance where performance is claimed;
5. idempotency/retry incident evidence when applicable;
6. the verified recovery-checkpoint identity;
7. the API/feature/pilot capability fingerprints and launch-plan hash used during the run;
8. the exact Git commit and CI run supporting the software build.

A successful pilot may state only the claims supported by those artifacts. It does not establish universal performance superiority, novelty, patentability, customer traction or production readiness beyond the declared environment.
