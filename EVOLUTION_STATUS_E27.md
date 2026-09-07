# MORPHEUS Evolution Status — E27

## Checkpoint

**E27 — Non-Creating Read-Only SQLite Snapshot Boundary Evidence**

This checkpoint records only evidence verified on exact implementation/test head `8fe6141001298a79c67118a81ffc79b4c43baf6d` by MORPHEUS CI run **1141** (`34169318731`), which completed successfully before this status document was created.

The evidence-bearing changes are:

- `d03f8b74be4c61aace420bf7f79e404c8372e543` — clarifies that an absent snapshot pair means absent rows inside an already initialized MORPHEUS SQLite database rather than relying on reader construction to create storage;
- `5028ab78b3322bcfa5f44a2337942fefe74288e3` — removes writable-adapter construction from the reader, requires a pre-existing database/schema, and opens observation connections using SQLite read-only URI mode plus `PRAGMA query_only = ON`;
- `8fe6141001298a79c67118a81ffc79b4c43baf6d` — verifies non-creating construction, non-mutating missing-schema failure, independent read-only URI enforcement, and preservation of coherent snapshot semantics.

## Verified capability

For the exercised local SQLite observation path, MORPHEUS now demonstrates that reader construction is itself observation-only with respect to database and schema creation.

The verified path demonstrates that:

- constructing a reader for a missing database beneath a missing parent fails closed without creating either the parent directory or database file;
- constructing a reader for an existing but schema-empty SQLite database fails closed without creating MORPHEUS tables;
- a valid pre-existing MORPHEUS database remains readable through the transaction-consistent fencing/resource snapshot path;
- every observation connection is opened using SQLite `mode=ro` URI semantics and is additionally hardened with `PRAGMA query_only = ON`;
- writes through the observation connection are rejected while `query_only` is enabled;
- deliberately disabling `query_only` on that same connection still leaves SQLite `mode=ro` as an independent write barrier;
- fencing/resource counter and version agreement checks from E25 remain enforced;
- automatic control, activation, and production traffic switching remain denied.

## Scientific and production truth boundary

E27 is **local SQLite connection-mode and construction-side-effect evidence only**.

SQLite `mode=ro` and `query_only` are not filesystem immutability, operating-system authorization, a security sandbox, arbitrary-database authorization, distributed read-only enforcement, or external-resource protection. A caller with a separate writable database connection or filesystem authority can still alter the same database.

This checkpoint does not establish distributed snapshot isolation, cross-host linearizability, consensus, leases, network-partition safety, storage-device or power-loss durability, safe cutover, live replacement, production failover, HA/SLA behavior, production activation, production traffic switching, or production readiness.

The exercised read-only failures are not a security certification and do not prove behavior for every SQLite extension, VFS, URI option, or environment configuration. No latency, throughput, scaling, benchmark-superiority, performance-superiority, novelty, patentability, state-of-the-art, or scientific-effect claim is made.

`automatic_control_allowed`, `activation_allowed`, and `traffic_switching_allowed` remain false.

## Next evidence dependency

The next dependency-ready gate is **read-only SQLite schema-contract validation and compatibility fail-closed evidence**.

E27 verifies that the two required table names exist before the reader is admitted, but table-name presence alone does not establish that the expected columns and key shape are compatible with the snapshot contract. A malformed, stale, or incompatible local schema can therefore pass the constructor-level name check and fail only when a snapshot query executes.

A useful next gate should validate the minimal schema shape required by the observation contract through read-only SQLite metadata inspection, fail closed during reader construction when required columns or key identity are absent/incompatible, leave the database unchanged, and preserve normal E27 observation semantics for the repository-created schema.

That gate would remain local SQLite schema-compatibility evidence only. It must not be generalized into migration correctness for arbitrary historical schemas, database security certification, corruption detection for all SQLite states, distributed schema agreement, production readiness, or performance claims.
