# MORPHEUS Evolution Status — E29

## Checkpoint

**E29 — Read-Only SQLite Key-Shape and Required-Nullability Compatibility Evidence**

This checkpoint records only evidence verified on exact implementation/test head `6834e2e9ab65a33f4d6ebfacf5f8be4473ff1774` by MORPHEUS CI run **1147** (`34172439233`), which completed successfully before this status document was created.

The evidence-bearing changes are:

- `9cc8ddff4ee3d7eba759d8f88b5e2bff6b4f3c0c` — extends the read-only SQLite snapshot constructor to require the ordered composite primary key `(resource_id, fencing_authority_id)` and NOT NULL on all observation-required columns;
- `6834e2e9ab65a33f4d6ebfacf5f8be4473ff1774` — verifies fail-closed construction for reversed/incomplete key shape and required-column nullability drift without modifying the exercised database.

## Verified capability

For the exercised local SQLite observation path, MORPHEUS now demonstrates constructor-time rejection when required table/column names are present but the key or nullability shape is incompatible with the snapshot contract.

The verified path demonstrates that:

- both reference tables must expose the ordered composite primary key `(resource_id, fencing_authority_id)`;
- observation-required columns must be declared `NOT NULL`;
- schemas with reversed or incomplete composite identity keys fail closed during reader construction;
- schemas allowing NULL in required persisted fencing/resource fields fail closed during reader construction;
- the malformed database remains unmodified in the exercised tests and unrelated preserved data remains intact;
- the repository-created schema continues to admit coherent transaction-consistent observations;
- automatic control, activation, and production traffic switching remain denied.

## Scientific and production truth boundary

E29 is **local SQLite key-shape/nullability metadata compatibility evidence only**.

This evidence does not prove declared type compatibility, CHECK-constraint equivalence, uniqueness semantics beyond the exercised primary key, trigger equivalence, migration correctness, corruption absence, compatibility with arbitrary historical schemas, or authorization/security properties. SQLite metadata inspection is not a generalized schema-verification theorem.

This checkpoint does not establish distributed schema agreement, cross-host linearizability, consensus, leases, network-partition safety, storage-device or power-loss durability, external-resource protection, safe cutover, production failover, HA/SLA behavior, production activation, production traffic switching, or production readiness.

No latency, throughput, scaling, benchmark-superiority, performance-superiority, novelty, patentability, state-of-the-art, or scientific-effect claim is made.

`automatic_control_allowed`, `activation_allowed`, and `traffic_switching_allowed` remain false.

## Next evidence dependency

The next dependency-ready gate is **read-only SQLite declared-type compatibility validation**.

E29 verifies required names, composite identity keys, and nullability, but SQLite can still expose those shapes while declaring incompatible storage types for fields whose MORPHEUS snapshot contract expects text or integer values. The next gate should inspect required column declarations through the existing read-only metadata path, fail closed at construction for incompatible declared types without modifying the database, and preserve successful observation for the repository-created schema.

That gate remains local SQLite metadata compatibility evidence only. It must not be generalized into arbitrary SQLite affinity semantics, migration correctness, corruption detection, security certification, production readiness, or performance claims.
