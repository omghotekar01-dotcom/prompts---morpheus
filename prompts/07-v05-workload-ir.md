# MASTER PROMPT #7 — VOLUME 5: WORKLOAD IR & COMPILER FRONT-END

## Mission
Build MORPHEUS's deterministic compiler front-end: validated/resolved MWS → typed, immutable, versioned `WorkloadIR` consumed by cost modelling, candidate synthesis, code generation, benchmarking and runtime adaptation. The source project defines MORPHEUS as a declarative-spec → workload model → cost model → composition search → code generation → runtime adaptation system. Preserve that architecture. Never let YAML dictionaries leak into optimizer logic.

## 1. Compiler contract
Pipeline:
`YAML/JSON/NL draft → MWS parse → schema validation → semantic validation → resolution → canonicalization → capability validation → lowering → WorkloadIR → analysis passes → optimizer`.

Hard invariants: invalid MWS never reaches IR; lowering is deterministic for fixed resolved MWS/default/profile versions; IR contains no UI metadata; references use stable IDs, not strings; units are canonical; derived values carry provenance; unsupported semantics fail closed; optimizer never reparses source text.

## 2. Required IR types
Implement explicit types, not generic maps:
`WorkloadIR, DatasetIR, FieldIR, OperationIR, UpdateIR, DistributionIR, AccessDistributionIR, ConstraintSetIR, ObjectiveIR, TemporalModelIR, MachineRequirementIR, Provenance, SourceSpan, Diagnostic, CapabilitySet, SemanticHash`.

Suggested root:
```text
WorkloadIR {
 ir_version; source_mws_version; semantic_hash;
 dataset; operations; constraints; objective; temporal;
 machine_requirements; derived; provenance;
}
```
All optimizer-visible structures should be immutable/value-semantic after construction.

## 3. DatasetIR
```text
DatasetIR { DatasetId id; string logical_name; RecordCount records; vector<FieldIR> fields; EstimatedBytes record_bytes; }
FieldIR { FieldId id; string logical_name; SafeSymbol symbol; ScalarType type; bool unique; bool nullable; Cardinality cardinality; DistributionIR values; AccessDistributionIR access; EncodedSize size; Provenance provenance; }
```
Canonical scalar types initially: signed/unsigned integers, float64, bool, string/bytes as actually supported. Do not pretend unsupported types work.

Compute and store when defensible: cardinality ratio, estimated encoded size, uniqueness consistency, fixed/variable-width status. Never fabricate unknown statistics.

## 4. Stable identity
Assign deterministic IDs by canonical declaration order or semantic identity. `FieldId`/`OperationId` must survive serialization and never depend on pointer address. Maintain logical name → ID symbol table only in front-end. Generated C++ symbol sanitization is separate from logical identity.

## 5. OperationIR
Use a discriminated union:
```text
PointLookup { field, hit_rate }
EqualityFilter { field, expected_selectivity }
RangeLookup { field, selectivity_model, bound_semantics }
PrefixLookup { field, prefix_length_model, expected_selectivity }
Membership { field, hit_rate }
Insert {}
Delete { key_field? }
Modify { field_probability_model }
```
Each operation has `OperationId`, name, normalized probability, optional absolute rate, result-cardinality estimate and provenance. Reads and writes become one normalized operation vector even if MWS authoring separates them.

## 6. Workload normalization
Weighted mode: require total ≈1 according to documented tolerance. Rate mode: preserve rates and derive probabilities `p_i=r_i/Σr`. Weighted+total-rate: derive absolute rates. Never silently normalize malformed research input. Record every transformation in resolution provenance.

Derived workload facts: read ratio, write ratio, dominant operations, fields touched, operation-field incidence matrix, read-only/append-only flags, expected output cardinalities and uncertainty flags.

## 7. Distribution IR
Typed variants: Uniform, Zipf, Normal, LogNormal, Categorical, Histogram, Empirical/ProfileRef, Hotset/access model, Unknown. Stored-value distribution and access-popularity distribution are different types/roles. Normalize probability tables and validate parameters before lowering. Profile references must resolve to immutable versioned artifacts.

## 8. Constraints
Represent hard and soft constraints explicitly:
```text
ConstraintSetIR {
 optional<Bytes> max_memory;
 map<OperationId, LatencySLA> latency;
 optional<Rate> min_throughput;
 optional<Duration> max_build_time;
 optional<uint32> max_secondary_structures;
 ...
}
```
Hard violations mean infeasible candidate, never automatic relaxation. Valid-but-infeasible is distinct from invalid specification.

## 9. ObjectiveIR
Discriminated union: `WeightedObjective`, `ParetoObjective`, `LexicographicObjective`. Expand presets before IR. Weighted objective stores exact normalized coefficients plus normalization policy/baseline reference. Operation frequency weights must never be confused with optimization-objective weights.

## 10. Temporal IR
Support `Stationary` first; model `Phased` and `TraceRef` explicitly when implemented. Phase vectors reference OperationIds and use canonical duration units. Runtime observations are not mutations of WorkloadIR; create `ObservedWorkloadSnapshot { base_hash, window, observed_mix, rates, confidence }`.

## 11. Units
Canonical internal units: bytes, nanoseconds, operations/second, dimensionless probability [0,1]. Human units belong at source/UI boundaries. Use strong wrappers (`Bytes`, `Nanoseconds`, `Probability`, `Rate`) to prevent accidental mixing.

## 12. Provenance and uncertainty
Every important statistic should be classifiable as `DECLARED | MEASURED | PROFILED | INFERRED | DEFAULT | UNKNOWN`. Where uncertainty is supported, use typed intervals/distributions rather than magic sentinel values. A derived fact should record dependencies when useful for explanation/research reproducibility.

## 13. Source mapping and diagnostics
Retain source path/span mapping outside or alongside semantic IR so optimizer explanations can point back to MWS paths. Diagnostic structure: code, severity, source path/span, message, suggestion, related entities. Categories: syntax/schema/semantic/resolution/capability/lowering/internal.

## 14. Front-end passes
Implement small deterministic passes:
1. Parse.
2. Schema validate.
3. Bind names/references.
4. Semantic validate.
5. Resolve defaults/presets/profiles.
6. Normalize units/mixes.
7. Capability check.
8. Lower typed IR.
9. Derive statistics.
10. Verify IR invariants.
11. Canonical serialize/hash.

Each pass has explicit input/output and diagnostics. Avoid one 2,000-line parser.

## 15. Semantic checks
At minimum: duplicate names; missing field refs; type-operation compatibility; cardinality bounds; uniqueness contradictions; invalid distributions; invalid selectivity/hit rate; workload total; all-zero objective; unsupported concurrency/durability; invalid phase mixes; unresolved profiles; impossible unit values. Prefix lookup on numeric field must fail. Unknown capabilities must not be silently ignored.

## 16. Capability system
Create machine-readable capability registry keyed by MORPHEUS version: supported MWS/IR versions, scalar types, operation kinds, temporal modes, objective modes, concurrency, durability and deployment targets. Front-end validation queries it. API/UI should expose same capability set so unsupported options are not offered.

## 17. Canonical serialization/hash
Create canonical JSON for IR with stable key/order semantics and deterministic float handling. `semantic_hash = H(canonical_semantic_IR)`. Exclude descriptions/timestamps/UI state. Include semantics that affect optimizer decisions, resolved defaults and referenced immutable profile versions. Hash is used for cache keys, experiments, artifacts and lock files.

## 18. IR versioning
`ir_version` is independent of MWS and product versions. Breaking layout/semantic change increments major version. Implement explicit migrations only when semantics are preserved; otherwise regenerate from source MWS. Never deserialize unknown major version optimistically.

## 19. Python/C++ boundary
Recommended control-plane front-end in Python/Pydantic, optimizer core in C++20. Do not pass loose JSON deep into C++. Define a versioned serialized IR contract (canonical JSON initially; protobuf/FlatBuffers only if justified). C++ decoder immediately constructs strong typed domain objects and validates invariants again at trust boundary.

## 20. Suggested Python modules
```text
backend/app/mws/{models,parser,validation,resolver,canonical}.py
backend/app/ir/{models,ids,units,lowering,passes,serialize,hashing,diagnostics}.py
```
C++:
```text
core/include/morpheus/ir/{WorkloadIR,DatasetIR,OperationIR,DistributionIR,Constraints,Objective,Units}.hpp
core/src/ir/{Decode,Verify,Derived}.cpp
```

## 21. APIs/CLI
`morpheus validate workload.yaml`; `morpheus mws resolve`; `morpheus ir emit`; `morpheus ir verify`; `morpheus ir hash`; optional `morpheus ir explain`.
HTTP: validate spec, resolve spec, emit IR, inspect diagnostics/capabilities. Synthesis jobs store exact resolved MWS hash + IR hash.

## 22. Compiler tests
Golden tests: MWS → resolved MWS → expected IR → expected hash. YAML/JSON semantic equivalence must yield same hash. Round-trip IR serialization preserves semantics. Property tests generate valid specs and verify invariants. Fuzz malformed YAML/JSON, extreme numbers, Unicode names, nesting and path-like strings. Every invalid fixture asserts stable diagnostic code.

## 23. Research-grade checks
Build deterministic synthetic IR fixtures independent of parser so search/cost-model tests do not depend on frontend. Store experiment workload IR hashes. Paper results must be traceable to exact MWS, IR, machine profile, primitive registry, cost model, search seed and benchmark artifacts.

## 24. Performance
Front-end correctness dominates micro-optimization. Still avoid quadratic name binding: symbol maps O(1) average; derived matrices should be sparse where appropriate. Cache lowering by resolved semantic hash. Never cache across incompatible capability/default/profile versions.

## 25. Security
Safe YAML loader; document/depth/count limits; no arbitrary remote fetch from MWS; artifact IDs instead of unrestricted URLs; sandbox local trace paths; sanitize generated symbols; never interpolate user strings into shell/code templates. IR decoder treats serialized data as untrusted.

## 26. Explainability bridge
Maintain mapping so a candidate explanation can say: `CFG-17 contains an exact-key structure for product_id because operation OP-1 accounts for 58% of normalized workload; memory estimate remains under the hard 256 MiB constraint.` Explanation facts must originate from IR/candidate evidence, not LLM invention.

## 27. MVP slice
Implement first: known record count; uint64/float64/string; point/range/equality/prefix; insert; memory hard constraint; weighted objective; stationary single-thread workload; strong IDs/units; canonical hash. Then add distributions, rates, updates, phases and profile refs. This matches the project's recommendation to prove a tractable end-to-end system before scaling the primitive library.

## 28. Acceptance gates
Do not call Volume 5 complete until: no optimizer accepts raw dicts; all source refs bind to IDs; all units canonical; all operation mixes validated; hard constraints typed; objective typed; IR immutable after creation; serialization deterministic; semantic hash stable; YAML/JSON equivalent inputs hash identically; invalid inputs never lower; unsupported semantics fail with capability diagnostics; golden/property/fuzz tests pass; Python↔C++ round trip works; optimizer can consume a synthetic WorkloadIR without knowing MWS syntax.

## 29. Build directive
Implement in this order: IDs+units → IR enums/types → symbol binding → semantic validators → resolver integration → lowering → invariant verifier → canonical serializer/hash → Python/C++ decoder → golden fixtures → CLI/API → frontend schema integration → profiling/observed-workload extensions.

## 30. North star
MWS is what the developer means. WorkloadIR is what MORPHEUS can prove it understood. The optimizer must operate only on that explicit, typed, reproducible meaning. If two equivalent specifications lower differently, or one specification lowers nondeterministically, the compiler front-end is wrong.

**NEXT: MASTER PROMPT #8 — VOLUME 6: PRIMITIVE DATA-STRUCTURE LIBRARY, CAPABILITY ALGEBRA & COMPOSITION CONTRACTS.**
