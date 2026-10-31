# MORPHEUS: user-owned dataset → DSA candidate selection (teacher demonstration)

**Scope:** This is an explanation of implemented functionality, not a guarantee of universal optimality or a claim of measured speedup without measurements.

## The 3-minute demonstration

1. Open **Real CSV Data**. Import a CSV or XLSX with *any* field names (for example, a shop's `Product,Cost,Available` or a school's `StudentID,Class,Mark`). Do not modify headings to match preconfigured examples.
2. Click **Analyze uploaded dataset using C++**. Show the real row count, inferred column types, distinct-value counts, source SHA-256 and the first page of *actual uploaded rows*. Use **Next 20** to demonstrate this is not a static screenshot. The browser-session file list lets you switch between uploads.
3. Open **All implemented DSA options**. The table comes from the optimizer's registered implementations in `backend/app/catalog.py`, cross-referenced with physical C++ source paths and operation capabilities. It is deliberately a *finite set of algorithms implemented by the team*, not a claim to know every possible data structure ever invented.
4. Add a workload operation; select a column from the file (never a hardcoded roll number, ATM ID or department). For read operations enter or select a value suggested from the actual visible rows, then **Query real records using C++** to show match count, selectivity, and matching rows. This is a **reference scan** of uploaded data, not the chosen index's measured performance.
5. Choose operation frequencies, memory budget, update frequency, objective weights and search budget. The operation dropdown contains compatible **implemented** read and write operation categories, not domain templates. Adding a write operation models anticipated write traffic; it does not edit the file.
6. Run **Search and compare actual DSA candidates**. Show (a) per-query eligibility and why incompatible structures were rejected, (b) the best *evaluated* feasible plan, (c) the **best evaluated alternative containing each eligible index**, and (d) *every* evaluated candidate and its modeled latency, index-memory estimate, score and feasibility reason. Export the actual run's candidates as JSON.
7. Download the generated C++20 header. Code generation does **not** imply that the downloaded header has been compiled and differential-tested on this exact uploaded dataset; that requires an actual C++ build/verification run.

## Demonstrate that the answer changes with the workload

Using the **same** dataset, compare:

- Exact lookups on a high-cardinality field: Robin Hood hashing is often a good modeled candidate because this registry assigns it fast exact-lookup priors.
- Range scans over an ordered/numeric field: a sorted array or B+ tree can enter and win depending on the query mix, memory and maintenance requirements.
- Filters on low-cardinality fields: the adaptive bitmap may be favorable, subject to its actual implementation eligibility gate.
- String-prefix queries: the trie is an available implementation; other structures without prefix-search capability are rejected.
- Many inserts/updates/deletes: change the declared write mix and objective to expose write-maintenance tradeoffs rather than treating read-only traffic as sufficient.

**Do not force a different winner artificially.** If Robin Hood or Bitmap still wins for similar workloads, explain that a stable ranking is a plausible outcome of the existing cost-model priors. To claim which index is *actually faster on the uploaded data*, run representative compiled C++ benchmarks with the file's values and record the machine, workload mix and repeated timing results.

## What comes from which source?

| Item | Source | Nature |
| --- | --- | --- |
| Column names, types, row count, cardinality | The uploaded file / compiled native C++ profiler | Actual derived dataset facts |
| Reference match counts, selectivity, preview | Submitted predicates over uploaded rows / native C++ reference probe | Actual data result, **not index performance** |
| Workload weights and future traffic | Teacher/operator inputs | Explicit assumptions unless observed logs were separately supplied |
| Available algorithms | Checked-in versioned primitive registry / implemented C++ indexes | Actual product capabilities; finite catalog |
| Predicted latency, score, memory, ranking | Model, constraints and native C++ search | **Modeled** unless matching calibration evidence exists |
| Generated C++ source | Config and source generation pipeline | Generated, not automatically compilation- or correctness-verified |
| Actual speedups | Repeated controlled benchmarks | Not implied by dataset upload or candidate ranking |

## Important real limitations

- The current upload adapter is bounded (currently a 15 MB request limit, a native parser bound and 100,000-row/64-column constraints); support for one lakh rows does **not** imply unbounded files. Files exceeding the effective parser/request limits are rejected, not silently sampled.
- Import alone does not determine the real query workload. A teacher must enter expected operations, or a separate genuine query log must be supplied; field names do not prove future usage frequencies.
- Native C++ handles CSV profiling, reference probing, registered implementations and bounded candidate search. The Python backend still holds part of the cost modeling and API orchestration. It would be incorrect to say the entire repository is 100% C++/Java/C today.
- A finite registry is proper engineering: adding another index requires building it in C++, declaring capabilities, registering model inputs and tests, and documenting its codegen support. Exposing an unimplemented option as if real would be deception.

## Questions a teacher may ask

**Where do the choices come from?** The primitive registry, its C++ implementations and capability checks. Each query's eligibility report lists every registered index and the actual reason for exclusion.

**Why Robin Hood again?** It has strong exact-lookup bootstrap coefficients. The answer is a model prediction; changing data cardinalities, query mix, weights or constraints can change the feasible space. The team should verify any real performance claim experimentally.

**Can I import a completely different dataset?** Yes, within documented CSV/XLSX, size, column and type limits. The profile, displayed records, field dropdowns and generated schema derive from that file, not fixed student records.

**Can you prove it searched the candidates?** Show the selected strategy, theoretical candidate count, number actually evaluated, truncation flag, candidate table and export for the current input SHA-256/spec hash.

**Can you guarantee the globally fastest data structure?** No. MORPHEUS identifies the best feasible evaluated modeled candidate under the submitted workload and available implemented options. Exhaustive search is still exhaustive only over that finite registered configuration space, and predictions are not measured benchmarks.
