# MORPHEUS: user-owned dataset → DSA candidate selection (teacher demonstration)

**Scope:** This is an explanation of implemented functionality, not a guarantee of universal optimality or a claim of measured speedup without measurements.

## Start the application on Windows

1. Open PowerShell in the MORPHEUS repository and run `git switch codex/dsa-course-core` if you are following this course branch.
2. Run `.\START-MORPHEUS.bat`. Keep its window open while presenting. It starts the local API and web app and verifies the native-engine bundle.
3. Open `http://localhost:5173`. Check the header says **Control plane Online**. If it says Offline, return to the launcher window, read its error, fix that before presenting, and use the refresh button once the services are ready.
4. Open **Machine Profiles** and confirm the C++ compiler is detected if you plan to demonstrate generated-code verification. The local C++ compiler is for verification; the already-built, SHA-256-verified engines handle profiling and synthesis.
5. Use a small, non-sensitive CSV/XLSX file you are allowed to show. Avoid private student, customer, or health information.

The starter card is a guide, not a failure indicator. **Check correctness** remains unavailable until a workload has produced generated code; after synthesis, the guide tells you the next action. Running synthesis does not itself claim that the generated code was compiled or verified.

The **Run complete demo** button on the Start page uses an editable synthetic workload. It is useful for a quick tour, but it does not analyze your CSV. For a real-data presentation, use **Real CSV Data** and follow the steps below.

## The 3-minute demonstration

1. Open **Real CSV Data**, select the file, and click **Analyze uploaded dataset using C++**. You can use any valid column names; the workflow profiles the uploaded file rather than requiring a special schema.
2. Show the measured row count, inferred column types, distinct-value counts, source SHA-256 and first page of the uploaded records. Use **Next 20** to show that the preview is read from the selected file. Nothing is being trained on or benchmarked by this profiling step.
3. Open **All implemented DSA options**. The table comes from the optimizer's registered implementations in `backend/app/catalog.py`, cross-referenced with physical C++ source paths and operation capabilities. It is deliberately a *finite set of algorithms implemented by the team*, not a claim to know every possible data structure ever invented.
4. Add an operation, select a column from the upload, then choose a real value from the preview and click **Query real records using C++**. Explain that this shows actual matching rows and selectivity from a **reference scan**, not a timing test of any index.
5. Pick the expected operation mix and constraints. For a useful comparison, first try exact lookups on a high-cardinality field, then try range searches or filters on an appropriate field. The operation weights represent your assumptions about future traffic; a write operation models expected writes and does not edit the uploaded file.
6. Click **Search and compare actual DSA candidates**. Walk through which structures are eligible, why other structures are rejected, and the candidates' feasibility and predicted cost scores. Export the candidate list if you want to show the run's record.
7. Open **Code Generator** to inspect the generated C++20. Return to **Synthesis Lab** and click **Run Full Verification** to compile and check the generated code's behavior. Present this as a correctness check, **not** as proof of speed.
8. Open **Experiment History** to show the saved run. Return to **Workloads**, change the operation mix, synthesize again, and compare the two candidate sets.

### Suggested narration

> “MORPHEUS profiles the data I supplied, then I describe how the application is expected to access it. It searches the data structures this project actually implements and explains the eligible candidates. The displayed costs are model estimates, not measured speedups. I can inspect the generated C++ and run separate compile and behavior checks.”

## Optional: show the standalone C example

The project also includes a small C11 binary-search lesson, separate from the C++ synthesis engine. When `gcc` is available on `PATH`, you can compile and run it without CMake:

~~~powershell
New-Item -ItemType Directory -Force build\c-dsa-demo | Out-Null
gcc -std=c11 -pedantic-errors -Wall -Wextra -Wpedantic -Werror -I core\include core\src\binary_search.c core\src\c_binary_search_demo.c -o build\c-dsa-demo\morpheus_c_binary_search.exe
.\build\c-dsa-demo\morpheus_c_binary_search.exe 8 1 4 8 12
~~~

Expected output: `Found 8 at index 2.` The values are supplied at the command line; the program does not contain a preselected result. See [C DSA learning example](C_DSA_LEARNING.md) for complexity and edge-case tests.

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
