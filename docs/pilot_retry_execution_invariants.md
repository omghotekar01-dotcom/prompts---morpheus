# Pilot Retry Execution Invariants

This document defines the next hardening boundary for the pilot idempotency workflow.

## Required invariants

1. A retry authorization is single-use and must not be consumed by more than one execution receipt.
2. All receipts in one execution history must preserve the same operation, idempotency key, and original request identity.
3. Receipt timestamps must be timezone-aware, canonicalized to UTC, and must not move backward.
4. An `AMBIGUOUS` execution is terminal for the current retry history until a fresh manual resolution is produced.
5. A successful or no-side-effect failure consumes the authorization and does not silently create new retry authority.
6. Duplicate receipt identities are invalid evidence.
7. Derived history summaries must be deterministic for identical ordered evidence.

## Next implementation milestone

Add an append-only execution-history verifier enforcing these invariants, followed by regression coverage for duplicate authorization consumption, lineage substitution, backward time, and unresolved ambiguity.
