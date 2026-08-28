# MORPHEUS WorkloadIR v1

Status: **implemented compiler contract**  
Implementation: `backend/app/workload_ir.py`  
Identity: SHA-256 of canonical JSON (`sort_keys=True`, compact separators, ASCII encoding)

## Purpose

MWS is the human-facing workload language. `WorkloadIR` is the immutable semantic input consumed by the synthesis pipeline. This boundary prevents YAML formatting, comments, key ordering, and presentation syntax from becoming optimization semantics.

The compiler flow is:

`raw YAML/JSON -> safe parser -> resolved WorkloadSpec -> WorkloadIR -> synthesis/search -> generated artifacts`

The IR is **not** benchmark evidence. Its hash proves which resolved workload semantics entered a decision.

## Versioning

Current version: `morpheus-workload-ir-v1`.

An incompatible semantic change must introduce a new IR version. Adding presentation-only MWS syntax must not change the IR hash when resolved semantics are unchanged.

## Top-level fields

| Field | Meaning |
|---|---|
| `ir_version` | WorkloadIR semantic schema version |
| `source_spec_version` | MWS version that produced the IR |
| `source_spec_hash` | SHA-256 identity of canonical resolved MWS |
| `name` | workload name |
| `record_count` | declared logical record count |
| `fields` | ordered typed field descriptors |
| `operations` | ordered normalized operation descriptors |
| `constraints` | resolved hard constraints |
| `objective` | resolved objective weights |
| `assumptions` | explicit compiler/default assumptions that can be reconstructed from the resolved model |

## Stable IDs

Fields use `f<ordinal>:<name>`, for example `f0:id`.

Operations use `q<ordinal>:<kind>`, for example `q2:range_scan`.

Ordinals are based on semantic declaration order and are part of the IR identity.

## Field typing

Every field keeps its original MWS type spelling in `source_type` and receives a compiler family:

- `integer`
- `floating`
- `string`
- `boolean`
- `opaque`

The family is used only for compiler compatibility reasoning. Generated C++ type lowering remains separately versioned in code generation.

## Operations

Operation weights are normalized so the IR sum is 1.0. The original relative weights therefore retain their meaning without making absolute numeric scale part of optimization semantics.

Each operation records:

- stable ID and ordinal;
- query kind;
- resolved field ID/name when applicable;
- normalized weight;
- resolved selectivity, result limit and prefix length when applicable;
- whether it is a mutation workload signal;
- a deterministic required access-pattern label.

Current access patterns:

| MWS kind | IR access pattern |
|---|---|
| `point_lookup` | `exact_key_lookup` |
| `range_scan` | `ordered_interval_scan` |
| `filter` | `equality_filter_postings` |
| `prefix_search` | `ordered_string_prefix` |
| `graph_traversal` | `graph_adjacency_traversal` |
| `insert` | `record_insert_maintenance` |
| `update` | `record_update_maintenance` |
| `delete` | `record_delete_maintenance` |

## Defaults and assumptions

MWS validation resolves defaults before lowering. WorkloadIR makes important compiler-visible assumptions explicit, including defaulted range/filter selectivity and default objective/constraint blocks when detectable from Pydantic field provenance.

This is not yet a full source-map/provenance system: comments, exact YAML spans and every syntactic omission are not preserved. That is an explicit limitation rather than hidden provenance.

## Mutation semantics

`insert`, `update` and `delete` operations are marked `mutating=true`. In the current generated record-store architecture they are workload/cost signals, not independent physical indexes. A generated mutation maintains every materialized query index. The synthesis cost model therefore charges maintenance across physical query members rather than pretending a mutation declaration creates another standalone index.

## Determinism contract

Two inputs with equivalent resolved MWS semantics must produce byte-identical canonical WorkloadIR JSON and the same WorkloadIR SHA-256 hash.

The following may change IR identity:

- record count;
- field ordering/name/type/cardinality;
- operation ordering/kind/field/relative weight/parameters;
- constraints;
- objectives;
- IR version;
- any resolved semantic default.

Whitespace, YAML comments, YAML-vs-JSON syntax, and object key order must not change IR identity.

## API

`POST /api/v2/workload/ir`

Request:

```json
{"spec_text":"<MWS YAML or JSON>"}
```

Response includes:

- `workload_ir_hash`
- canonical `workload_ir`
- `source_spec_hash`
- evidence state `DETERMINISTIC_SEMANTIC_LOWERING`
- an explicit truth boundary saying IR identity is not performance evidence.

Synthesis results also carry `workload_ir_hash` and `workload_ir_version`, and stored synthesis-result JSON therefore binds downstream decision evidence to the canonical compiler input.

## Current limitations

1. Full token/span source maps are not implemented.
2. The IR does not yet model temporal phases, distributions beyond current MWS fields, NUMA/cache topology, persistence semantics, transaction isolation, or distributed consistency.
3. The IR hash establishes semantic identity, not correctness of the cost model or generated code.
4. Changing MWS defaults can change resolved semantics; such changes require compatibility review and should be reflected in versioning when externally observable.

These limits are intentional and must remain visible in research and product claims.
