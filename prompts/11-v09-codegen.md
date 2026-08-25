# MASTER PROMPT #11 — VOLUME 9: CODE GENERATION, COMPILATION, CORRECTNESS VERIFICATION & ARTIFACT PIPELINE

## Mission
Turn a selected ConfigurationIR into real, reproducible, production-shaped executable code. MORPHEUS must generate an implementation—not merely recommend structures. Generated artifacts must compile, expose a stable logical API, preserve semantics under mutations, pass differential correctness tests and carry complete provenance linking them to workload/configuration/model/search evidence.

## 1. Trust boundary
Only validated ConfigurationIR enters codegen. Templates never consume raw MWS/YAML or LLM prose. Codegen must be deterministic for fixed ConfigurationIR + generator version + toolchain profile.

## 2. Artifact pipeline
`ConfigurationIR → GenerationPlan → source tree → formatter/static checks → configure → compile → unit/differential tests → benchmark → package → ArtifactManifest`.
Any failure returns structured stage diagnostics; never call a non-compiling candidate “generated successfully.”

## 3. GenerationPlan
Explicit intermediate plan containing logical schema, safe symbols, selected primary store/index components, constructor/build order, query routes, maintenance actions, API signatures, required headers/libraries, build settings and test generation plan. This decouples optimizer configuration from language-specific templates.

## 4. Stable generated API
Generate operation-specific facade based on WorkloadIR, e.g. `find_by_id`, `range_by_price`, `filter_category`, `prefix_name`, `insert`, `erase`, `update`. User-facing API semantics remain stable when physical configuration changes. Never force consumers to call `BPlusTree` directly.

## 5. C++20 MVP
Generate standard C++20 with CMake/Ninja. Keep dependencies minimal. Primitive implementations can be internal reusable library components linked/instantiated by generated facade rather than duplicating thousands of lines per artifact.

## 6. Repository-size discipline
Generated artifacts belong in build/output cache, releases or ignored workspace—not the lightweight prompts repo. Do not commit compiled binaries, benchmark raw datasets, object files or duplicated generated sources to the prompt repository.

## 7. Record model
Generate strongly typed record struct/schema from FieldIR with safe C++ types and sanitized identifiers. Maintain mapping from logical names to generated symbols in manifest. Handle variable-length strings/ownership explicitly.

## 8. Record identity
Use stable internal RecordId contract so secondary indexes point to records safely. Define invalidation/lifetime rules. If vector relocation would invalidate pointers, do not store raw unstable pointers.

## 9. Construction
Generated store accepts records and builds primary/secondary structures in deterministic order. Validate uniqueness/preconditions and fail cleanly on invalid input. Record build timing separately from runtime operations.

## 10. Query routing
Each generated method follows selected AccessRoute exactly. Direct route invokes selected index; filter→verify checks exact predicate; intersection combines RecordId sets correctly; scan fallback only when configuration explicitly contains it.

## 11. Result semantics
Specify result type/order/duplicates. Exact unique lookup returns optional record/reference; equality/range/prefix may return stable vector/iterator of records/IDs. Do not accidentally change order semantics when swapping primitives.

## 12. Mutations
Insert/delete/modify update primary storage and every dependent index. Define transactional logical sequence for single-thread MVP: prevalidate → perform changes with rollback strategy or safe ordering → commit. Tests inject failures where feasible to ensure no partially inconsistent state.

## 13. Exception/error policy
Choose one consistent generated API policy (exceptions, expected/result type, status enum). Avoid process termination for normal invalid input. Allocation/logic failures surfaced appropriately.

## 14. Parameter embedding
All selected primitive parameters are explicit generated constants/configuration values and manifest entries. No hidden generator defaults that differ from ConfigurationIR.

## 15. Template architecture
Use small composable templates: record, store facade, primitive bindings, route methods, maintenance methods, CMake, tests, benchmark adapter, manifest. Avoid one giant Jinja template.

## 16. Template safety
Only whitelisted template variables; sanitize identifiers/path names; never render arbitrary user code; no shell interpolation; build subprocess uses argument arrays; sandbox output directory.

## 17. Generator versioning
`generator_version`, template bundle hash and primitive library commit/version recorded. Changing generated semantics requires version bump.

## 18. Build profile
Manifest records compiler path/family/version, flags, build type, target architecture, dependencies and CMake/Ninja versions. Benchmark artifacts must be reproducible.

## 19. Build isolation
Compile each candidate in isolated directory/container when practical. Set time/resource limits. Generated code is system-produced but still treat compile execution as a security boundary in SaaS.

## 20. Compiler diagnostics
Capture stdout/stderr and normalize into structured `BuildDiagnostic` with stage, file/line if available and log artifact. Search may mark candidate `CODEGEN_UNSUPPORTED` or `BUILD_FAILED`; it must not silently replace with another unrecorded design.

## 21. Reference implementation
Generate/use a simple obviously-correct reference store independent of selected structures. It can use scans/maps and need not be fast. This is the oracle for differential tests.

## 22. Generated correctness traces
From WorkloadIR generate deterministic seeded operation sequences containing hits/misses, boundaries, duplicates, inserts/deletes/modifies and empty/small datasets. Run candidate and reference; compare after operations.

## 23. Boundary cases
Zero/one records if schema permits; min/max numeric keys; absent key; duplicate nonunique key; range empty/single/full; prefix empty/full/none according to declared semantics; delete absent; update indexed field; strings with allowed encoding edge cases.

## 24. Property-based testing
Generate random datasets/traces within spec. Assertions focus on semantic equivalence. Shrink failing cases if framework permits and save minimal repro artifact.

## 25. Sanitizers
Debug/research builds should run AddressSanitizer/UndefinedBehaviorSanitizer where supported. ThreadSanitizer when concurrency arrives. Sanitizer pass status belongs to validation manifest.

## 26. Static analysis
Optional clang-tidy/cppcheck profile. Formatting via clang-format. Do not gate MVP on zero stylistic warnings, but correctness/security warnings matter.

## 27. Benchmark adapter
Generated artifact exposes standardized benchmark interface so finalist benchmarking uses same operation semantics/workload generator across configurations. Prevent each candidate from receiving a different benchmark implementation.

## 28. Dead-code prevention
Benchmark consumes outputs/checksum; compiler cannot optimize queries away. Validate benchmark trace before timing and separate setup.

## 29. ArtifactManifest
```text
artifact_id; workload_hash; ir_hash; configuration_hash;
search_job_id; model_version; machine_profile_hash;
generator_version; primitive_registry_hash;
source_hash; compiler/version/flags; build_hash;
correctness_status; sanitizer_status; benchmark_refs;
created_at;
```
This is the chain of custody for every result.

## 30. Content-addressed cache
Cache generated source/build by semantic inputs. Never reuse binary across incompatible compiler/target/dependency profile. Verify hashes.

## 31. Packaging
MVP outputs: source package + static/shared library or executable + headers + manifest + README usage snippet. REST wrapper is separate deployment layer, not mandatory inside core generated library.

## 32. Python binding
Optional pybind11 wrapper generated from stable facade. Do not expose primitive internals. Python tests compare same semantics.

## 33. REST service wrapper
For demo, FastAPI process can invoke generated library/binary. API schema derives from logical operations, not physical structures. Do not rebuild compiler toolchain on every request; synthesis/deployment jobs are asynchronous.

## 34. Hot swap future
Runtime adaptation requires stable facade/ABI or indirection layer. MVP can rebuild/restart/offline switch. Never market offline restart as live zero-downtime hot swap.

## 35. Version compatibility
Generated artifact declares compatible WorkloadIR/ConfigurationIR/primitive runtime versions. Loader rejects mismatch.

## 36. Failure taxonomy
`GENERATION_FAILED`, `FORMAT_FAILED`, `CONFIGURE_FAILED`, `COMPILE_FAILED`, `LINK_FAILED`, `CORRECTNESS_FAILED`, `SANITIZER_FAILED`, `BENCHMARK_FAILED`, `PACKAGE_FAILED`. Store reason/evidence.

## 37. Search integration
A model-feasible candidate can still fail codegen. Search result must distinguish predicted feasibility from artifact validation. Final deployable selection requires generation+correctness pass; benchmark validation depending policy.

## 38. Correctness-before-speed
If fastest candidate fails differential tests, reject it. Never weaken test to preserve benchmark story.

## 39. Repro command
Artifact should include machine-readable reproduction metadata and CLI command conceptually: `morpheus artifact reproduce <manifest>`; it resolves exact versions or reports unavailable dependency rather than silently using latest.

## 40. Deterministic source
Same inputs should produce byte-identical source where timestamps excluded. Keep generated timestamps in manifest, not source bodies if they break content hash.

## 41. Test fixtures
Golden generated source for tiny configurations; compile tests for each primitive combination; mutation integration tests; identifier sanitization; malicious strings/path tests; cross-language serialization tests.

## 42. Performance regression
Generated facade overhead should be benchmarked against direct primitive invocation. Establish acceptable overhead budget and detect regressions in CI.

## 43. Demo flow
Submit workload → show selected composite configuration → click “Generate” → actual build logs → correctness green → benchmark → download/use library → execute sample query. Every UI state comes from real pipeline status.

## 44. Research reporting
Report codegen success rate across candidate configurations, correctness failure count, generated-source size/build time and facade overhead. This proves end-to-end synthesis reliability beyond optimizer accuracy.

## 45. MVP
Generate C++ for primary record vector/store + hash exact lookup + B+ tree/sorted range route; insert; tests; CMake; benchmark harness; manifest. Expand after this works end-to-end.

## 46. Acceptance gates
ConfigurationIR-only input; deterministic GenerationPlan; safe symbols/templates; stable logical API; all indexes maintained on writes; reference oracle; differential/property tests; compile/link pass; sanitizer profile; standardized benchmark adapter; provenance manifest; content hashes; no binary/raw artifact committed to prompts repo; final deployable candidate reconstructable.

## Build order
GenerationPlan → safe symbol/type mapping → facade template → hash/sorted/B+ bindings → CMake → reference store → generated tests → compile runner → differential traces → manifest/cache → benchmark adapter → package → Python/REST wrapper → migration-compatible facade.

## North star
A MORPHEUS decision becomes scientifically and commercially meaningful only when it can cross the boundary from “candidate configuration” to “correct executable artifact.” Code generation is therefore not a presentation feature; it is part of the proof that synthesis is real.

**NEXT: MASTER PROMPT #12 — VOLUME 10: RUNTIME MONITORING, WORKLOAD DRIFT, HYSTERESIS, MIGRATION & SAFE ADAPTATION.**
