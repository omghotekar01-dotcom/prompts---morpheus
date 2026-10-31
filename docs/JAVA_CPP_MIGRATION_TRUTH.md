# MORPHEUS: Native Java + C++ core migration — implementation truth

## Primary purpose, unchanged

MORPHEUS selects an explainable **physical data-structure plan** for a
*user-supplied* dataset and declared operation mix under hard constraints.
It must show every registered eligible alternative, model provenance, candidate
ranking, generated code and evidence separately. Data types, schema names,
cardinality, query predicates, memory budgets and operation frequencies must
come from input, never from a student/ATM template or a preselected winner.

**As of this change, the entire historical application has NOT been ported to
Java/C/C++.** Treat that as an explicit engineering gap, not a misleading
"100% done" badge.

## Implemented architecture

| Layer / computation | Implementation | Truth / limitation |
| --- | --- | --- |
| Robin Hood hash, B+ tree, sorted array, bitmap, trie, CSR graph | C++20, `core/include/morpheus` | Real implemented finite registry, not universal catalog |
| User-supplied CSV profile, row paging and exact reference predicates | Native C++20 CSV process | Actual uploaded rows; reference scan does not benchmark the index |
| Bounded exhaustive/beam/greedy configuration exploration | C++20 `morpheus_native_search` | Real candidate enumeration within hard search budget |
| **Final objective scoring and hard memory/p99-proxy/build gates** | **Java 17+** `com.morpheus.dsa.PlanScorer` when compiled and enabled | Independent runtime process, per-candidate inputs, versioned `MORPHEUS_JAVA_SCORE_V1` protocol |
| Query model estimates, machine-specific calibration lookup, uncertainty and data-to-IR parsing | Python compatibility layer | **Still to migrate**; estimates are not real timings unless explicitly supported by measured calibration |
| Input validation, model/API persistence, backend orchestration | FastAPI / Python | Legacy API/bridge still present |
| Dashboard, file upload, candidate tables | React / TypeScript | UI only; no invented DSA outcome |

The Java scorer does not infer workload frequencies from dataset columns. A
teacher must enter operation mix or provide a genuine trace. The Java scorer
receives the candidate's **model metrics and constraints**, computes weighted
scores and a hard rejection bitmask, and returns them to the adapter.
It never decides winners by keyword, project category, or column name.

## Reproduce the Java engine without the website

Use a JDK 17+:

~~~powershell
New-Item -ItemType Directory -Force build\java | Out-Null
javac --release 17 -encoding UTF-8 -d build\java java\src\com\morpheus\dsa\PlanScorer.java java\test\com\morpheus\dsa\PlanScorerSelfTest.java
java -cp build\java com.morpheus.dsa.PlanScorerSelfTest
~~~

Expected marker: `JAVA_PLAN_SCORER_TESTS_PASS`. It verifies differing memory
budgets, changing update pressure, all hard-constraint bits, and rejection of
nonfinite metrics.

Enable Java in an already configured backend:

~~~powershell
$env:MORPHEUS_PLAN_SCORER = "java"
$env:MORPHEUS_JAVA_CLASSES = (Resolve-Path build\java).Path
~~~

The Windows launcher compiles Java automatically if both `javac` and `java`
are on PATH; otherwise it clearly reports that legacy Python scoring is in
use. The launcher separately requires the native C++20 optimizer and profiler,
either compiled on the host or verified against the CI binary manifest.
No Java source files are compiled or evaluated using a language model.

## Strict scoring contract

Protocol on standard input:

~~~text
MORPHEUS_JAVA_SCORE_V1
2
0.1 -1 -1 100
1 0.15 0.2 0.05
0.09 0.08 1 0.17
0.08 0.13 2 0.17
~~~

Output is `OK 2` followed by one `R <score> <rejection-bitmask>` per candidate.
Bit 1 means memory exceeded, bit 2 modeled latency/proxy exceeded and bit 4
build-time exceeded. Multiple bits combine. All floats and bounds are
validated; unsupported, truncated or nonfinite responses are refused.
The Python adapter only translates to/from existing Pydantic/API shapes.

The original legacy Python evaluator is still retained until full native
parity and tests are complete. `MORPHEUS_PLAN_SCORER=java` means **fail
closed** if a compiled Java scorer is missing; `auto` uses Java if built;
`python` explicitly selects compatibility scoring.

## Remaining steps before claiming 100% Java/C++ domain logic

1. Port all bootstrap and calibrated per-primitive **cost estimation** from
   `backend/app/cost_model.py` and `index_footprint.py` into a versioned
   compiled numerical/model module. Preserve uncertainty/evidence identity
   (machine, implementation, scale and access distribution), and check
   differences against the frozen research datasets.
2. Port the remaining **physical candidate evaluation and Pareto calculation**
   and eliminate redundant Python scoring once byte/precision-bound parity
   and real benchmark coverage pass. Reject invalid near-boundary memory and
   p99 decisions, not merely display a winner.
3. Build a primary **Java control-plane application** for workload parsing,
   validation, candidate evidence, versioned state, auth and API if the
   requirement is that Python be only ML glue. This is not finished merely by
   adding a Java scorer file.
4. Migrate **schema-derived code generation, compile/differential verification,
   workload-trace ingestion and candidate implementation registry semantics**
   to Java/C++ where appropriate. Prevent UI-only / stub Java components.
5. Run full cross-platform C++ sanitizer, Java tests, offline CSV/XLSX
   arbitrary-schema cases, build/refresh of the Windows native bundles, full
   backend+frontend integration, and a non-toy dataset performance comparison.
6. Only after these gates pass and Python has no optimization decisions should
   a completion claim such as "100% native domain logic" be made. The website
   remains TypeScript by design.

## Teacher explanation

- **Who defines the options?** The implementation registry documents which
  physical indexes actually exist; developers register implementations and
  capabilities. The teacher selects *workload*, not an artificially forced
  index. Ineligible indexes remain visible with the reason they were excluded.
- **Why the same winner?** The same workload and bootstrap cost priors can
  rationally give the same winner. Vary input columns/cardinality, memory,
  operation mix and objective; record the resulting candidate table rather
  than guaranteeing a different label.
- **Where is Java?** Candidate scores and hard constraints are checked by a
  real Java process when enabled, with a standalone self-test and CI job.
- **Where is C++?** Actual implemented data structures, real CSV queries and
  bounded search are compiled C++20.
- **Is the fastest option proven?** No: the winner is the best *evaluated*
  **modeled** plan. Actual fastest-on-machine claims require repeated
  representative C++/Java measurements against the uploaded dataset.
