# MORPHEUS Evolution Status — E28

## Checkpoint

**E28 — Read-Only SQLite Required-Column Schema Compatibility Evidence**

This checkpoint records only evidence verified on exact implementation/test head `52547338c65367808676cd90b7102fb716b73f7c` by MORPHEUS CI run **1144** (`34172017189`), which completed successfully before this status document was created.

The evidence-bearing changes are:

- `2128c9833633d9b401a113437de9aaa666f7dfc5` — extends the read-only snapshot constructor to inspect SQLite metadata and require every column consumed by the fencing/resource observation contract;
- `52547338c65367808676cd90b7102fb716b73f7c` — verifies fail-closed construction for missing required columns without modifying the drifted database, while preserving successful observation against the repository-created schema.

## Verified capability

For the exercised local SQLite observation path, MORPHEUS now demonstrates constructor-time rejection when either required table is absent or when a required observation column is absent.

The verified path demonstrates that:

- schema validation runs through the same read-only SQLite connection boundary used by E27;
- the fencing table must expose `resource_id`, `fencing_authority_id`, `fencing_counter`, and `version`;
- the protected-resource table must expose `resource_id`, `fencing_authority_id`, `resource_version`, `value`, `last_mutation_id`, and `last_fencing_counter`;
- a drifted schema missing a required column fails closed during reader construction rather than at the first snapshot query;
- the drifted database remains byte-identical in the exercised test and unrelated preserved data remains intact;
- the repository-created schema continues to admit coherent transaction-consistent observations;
- automatic control, activation, and production traffic switching remain denied.

## Scientific and production truth boundary

E28 is **local SQLite table/column-presence compatibility evidence only**.

Column-name presence does not by itself prove key identity, nullability, declared type affinity, CHECK constraints, uniqueness semantics, trigger behavior, migration correctness, corruption absence, or compatibility with arbitrary historical schemas. SQLite metadata inspection is not a database security certification or a generalized schema-verification theorem.

This checkpoint does not establish distributed schema agreement, cross-host linearizability, consensus, leases, network-partition safety, storage-device or power-loss durability, external-resource protection, safe cutover, production failover, HA/SLA behavior, production activation, production traffic switching, or production readiness.

No latency, throughput, scaling, benchmark-superiority, performance-superiority, novelty, patentability, state-of-the-art, or scientific-effect claim is made.

`automatic_control_allowed`, `activation_allowed`, and `traffic_switching_allowed` remain false.

## Next evidence dependency

The next dependency-ready gate is **read-only SQLite key-shape and required nullability compatibility validation**.

E28 verifies required column presence, but a schema can expose all expected names while changing the composite identity key or allowing NULL in fields that the MORPHEUS snapshot contract treats as mandatory. The next gate should inspect `PRAGMA table_info` metadata read-only, require the ordered composite primary key `(resource_id, fencing_authority_id)` on both reference tables, require NOT NULL on all observation-required columns, fail closed at construction for incompatible shapes without modifying the database, and preserve successful observation for the repository-created schema.

That gate would remain local SQLite metadata compatibility evidence only. It must not be generalized into arbitrary migration correctness, CHECK-constraint equivalence, trigger equivalence, corruption detection, distributed schema agreement, production readiness, or performance claims.
