# MORPHEUS: user-owned dataset → DSA candidate selection (teacher demonstration)

**Scope:** This is an explanation of implemented functionality, not a guarantee of universal optimality or a claim of measured speedup without measurements.

## Start the application on Windows

1. In PowerShell, go to the repository folder. If you need the course branch, switch to it once with `git switch codex/dsa-course-core`.
2. Run `.\START-MORPHEUS.bat` and leave its window open. The launcher checks the native-engine bundle, prepares the local API and frontend, then starts the services.
3. Open `http://localhost:5173`. Wait for startup checks and confirm the top bar says **Control plane Online**. Do not present synthesis or verification while it says **Offline** or **Locked**.
4. If the backend is offline, read the launcher window first; fix its reported startup problem, then use the top-bar refresh button. **Open degraded workspace** is for UI inspection only; it does not make the backend work.
5. If you plan to run generated-code verification, go to **More tools → Machine Profiles** and check that a C++ compiler is detected. The C++ compiler is for verification; the native engines used for profiling/search are separately built and verified by the launcher.
6. Use the included synthetic workbook at `demo-data\MORPHEUS_DSA_100K_Demo.xlsx` for the repeatable data demo. Do not display private student, customer, health, or other sensitive data.
7. If startup reports that the native C++ engines do not match the source, stop and follow `docs\WINDOWS_NATIVE_STARTUP.md`. Do not replace only one executable or copy an arbitrary artifact.

## The 3-minute quick demo (sample workload)

1. On **Home**, explain MORPHEUS in one sentence: it compares implemented data structures against an explicitly described workload.
2. Click **Try a sample workload**, or choose one of the sample cards. This loads an editable synthetic workload; it does not profile a file or prove real application traffic.
3. On **Workload**, point out the operations, fields, and frequency weights. Explain that the weights are assumptions unless supplied from real traffic. Click **Run current workload**.
4. On **Results**, show the selected candidate, alternatives, operation-to-structure routes, feasibility, and modeled scores. Explain that a modeled winner is not proof of the fastest real implementation.
5. Open **Code & Verify**. Inspect the generated C++20 artifact and click **Run Full Verification**. Report the actual compile and behavior gate results; neither gate is a speed test.
6. Open **More tools → Saved runs** to show that a real synthesis run was saved. **Resume run** reloads it; **Explain** opens its evidence-grounded explanation.
7. For a short algorithm lesson, open **Learn DSA** and contrast exact lookup, ordered range search, prefix search, bitmap filtering, and graph traversal.

## Full real-workbook demonstration

1. From **Home**, click **Start with real data** (or choose **Data** in the sidebar).
2. Click **Choose your own dataset** and select `demo-data\MORPHEUS_DSA_100K_Demo.xlsx`. MORPHEUS reads the active worksheet. The importer is bounded: 15 MB, 100,000 records, and 64 columns.
3. Click **Analyze uploaded dataset using C++**. Wait for the real profile to finish before continuing.
4. Show the reported row count, column names/types, distinct-value counts, source fingerprint, and the first page of records. Click **Next 20** to inspect more rows. These are facts derived from the uploaded file; this step does not train a model or benchmark indexes.
5. In **Learn DSA**, briefly explain why different operations favor different structures. Return to **Data**.
6. Add a point lookup on a high-cardinality field such as `SKU`, or a range scan on a numeric field such as `Unit_Price_INR`. Choose a value visible in the preview and click **Query real records using C++**. This returns actual matches from a reference scan; it is not an index-speed comparison.
7. Set the expected operation mix and constraints. The weights describe expected traffic; a declared write operation models workload pressure and does not edit the workbook.
8. Click **Search and compare actual DSA candidates**. Explain that the registry is finite and implemented: candidates appear only when their capabilities fit the operation and constraints. Review why candidates were eligible or rejected and show the evaluated count/truncation evidence.
9. Explain the evidence correctly: row/profile and reference-query results come from the supplied data; candidate cost/rank is modeled unless matching calibration exists. Use **Export real candidate comparison (JSON)** if you need a saved record.
10. Inspect or download the generated C++ header. Then open **Results** and **Code & Verify** to inspect the artifact and run compile/behavior checks. Do not call verification a performance benchmark.
11. Open **More tools → Saved runs** and resume the run if useful. Change the workload mix and run again to compare decisions; do not force a different winner just for the demo.

**If something is not ready:** keep the launcher window open, read its error, and correct that before continuing. The web page returning does not by itself mean the API or native engines are ready. If only the frontend is available, show the UI and Learn DSA page but do not claim a live profile, synthesis result, or verification.

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
