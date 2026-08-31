# Pilot Retry Execution Invariants

Status: **implemented deterministic retry-evidence validation stack; not automatic live retry authority**.

This document defines the hardening boundary for pilot idempotency retry evidence. It applies only after an ambiguous/no-side-effect incident has gone through the explicit operator-resolution and authorization workflow. The modules described here validate provenance and single-use semantics; they do not call the target system or silently retry a request.

## Required invariants

1. A retry authorization is single-use and must not be consumed by more than one execution receipt.
2. All receipts in one execution history must preserve the same operation, idempotency key hash and original request identity.
3. Receipt timestamps must be timezone-aware, canonicalized to UTC, and must not move backward.
4. An `AMBIGUOUS` execution is terminal for the current retry history until a fresh manual resolution is produced.
5. A successful or no-side-effect failure consumes the authorization and does not silently create new retry authority.
6. Duplicate receipt identities are invalid evidence.
7. Derived history summaries must be deterministic for identical ordered evidence.
8. Authorization sequence identities must remain contiguous where the ledger protocol requires sequential retry authority.
9. Execution fences must bind the exact authorization, registry consumption evidence, request lineage and executor identity before an execution outcome can be represented as valid evidence.
10. Seals/freshness checks may reject stale or substituted retry-ledger evidence; a valid seal is not permission to perform another retry.

## Implemented evidence components

The repository contains tested modules for:

- manual idempotency resolution receipts/chains;
- retry authorization and bounded retry-budget evidence;
- authorization consumption registries;
- fresh authorization leases and lease-consumption evidence;
- retry execution receipts and execution fences;
- append-only execution-history validation;
- ordered retry execution ledgers;
- ledger sealing, seal verification and verification-freshness checks;
- deterministic top-level evidence-chain construction/verification.

The exact schemas remain versioned in their modules and tests. Evidence identities use SHA-256 digests and validators fail closed on lineage substitution, duplicate identities, invalid state transitions, time-order violations and malformed authorization semantics.

## Live-system boundary

These components are **offline/control-plane evidence utilities**. Their existence does not mean MORPHEUS has permission to:

- automatically retry an ambiguous external side effect;
- infer that a target-system side effect did or did not occur;
- bypass manual resolution;
- create unlimited retry authority;
- provide distributed exactly-once transactions;
- coordinate retries across multiple MORPHEUS nodes;
- claim cross-process production execution safety.

The versioned `/api/v2/pilot/synthesize` path retains its durable single-node idempotency contract. Unresolved ambiguity fails closed. A confirmed existing side effect keeps the original key blocked. A confirmed no-side-effect resolution may make a later explicit retry possible, but the retry remains an operator/client action and must satisfy whichever authorization/evidence protocol is declared for that integration.

## Remaining productization milestone

The next meaningful milestone is **not another evidence wrapper by itself**. It is to connect a target-specific, explicitly authorized retry executor to these existing evidence contracts under a separately declared integration scope, with:

1. a concrete external side-effect model;
2. target-specific reconciliation/read-after-write checks;
3. bounded retry policy;
4. auditable operator authorization;
5. crash/restart recovery tests;
6. concurrency tests proving one authorization cannot execute twice;
7. a rollback/compensation model where applicable;
8. an explicit statement of what remains impossible to guarantee.

Until such an executor is separately implemented and verified, the evidence stack must continue to report that automatic live retry authority is not granted.
