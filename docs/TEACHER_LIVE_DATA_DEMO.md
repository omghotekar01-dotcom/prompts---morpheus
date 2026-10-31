# MORPHEUS — teacher-led arbitrary dataset demonstration

The **Real CSV Data** screen supports user-owned CSV and Excel .xlsx uploads rather than a student-only or ATM-only schema.

## Live demo

1. Upload a file, then click **Analyze uploaded dataset using C++**. Show the actual row count, the original uploaded column headings, the unique C++-safe identifier mapped from each heading, detected types and exact distinct counts.
2. Click **Next 20** / **Previous 20** to browse the actual uploaded records, parsed by the C++ reader. The API records the SHA-256 of the original submitted source.
3. Open **All implemented DSA options**. Show each implemented primitive, implementation ID and physical C++ file. The bounded registry is defined in backend/app/catalog.py and backend/app/primitive_manifest.py; it does not manufacture an unlimited catalog of non-existent implementations.
4. Define a lookup, equality filter, ordered range or string-prefix query using ANY uploaded column. Use **Query real records using C++** to count actual matches and inspect matching rows; for filter/range this sets observed selectivity.
5. Change relative operation frequencies, constraints, candidate search strategy and memory budget. Run the optimizer again. The engine shows all eligible structures for each query plus excluded ones and their reasons, theoretical combinations, evaluated finalists, feasible and rejected candidates, scores and uncertainty.
6. Download the chosen plan's generated C++20 header. It contains the actual schema field names and selected index members. This header is labeled GENERATED_NOT_COMPILE_OR_BEHAVIOR_VERIFIED and must be compiled and checked before claiming correctness.
7. Upload a different CSV with 10, 1000 or up to 100000 records, completely unrelated columns, and repeat the same steps.

## Real physical catalog

| Implementation | Operations | Source |
| --- | --- | --- |
| Robin Hood Hash | Point lookup, mutations | core/include/morpheus/structures.hpp |
| Sorted Array | Point lookup, range and equality filter | core/include/morpheus/mutable_indices.hpp |
| B+ Tree | Point lookup, range, equality filter and mutations | core/include/morpheus/bplus_tree.hpp |
| Radix Trie | String prefix and point lookup | core/include/morpheus/mutable_indices.hpp |
| Compressed Bitmap | Equality filter | core/include/morpheus/compressed_bitmap.hpp |
| CSR Graph | Graph traversal in advanced workloads | core/include/morpheus/csr_graph.hpp |

Alternatives enter the search only when they support the operation and the field's properties. Filters can use a duplicate-preserving B+ Tree or Sorted Array as well as the Bitmap. Candidates are ranked by computed model scores and constraints, not rotated to create artificial variation.

## What is real and what is estimated?

- Native C++20 parses the submitted CSV and returns actual statistics, record pages and reference-scan matches.
- The query reference scanner performs an actual full scan, **not** a benchmark of the winning index.
- Compiled C++20 performs bounded candidate enumeration and beam/greedy configuration search.
- Python remains the API, spreadsheet I/O adapter, candidate cost estimator, final scorer and C++ code-generation orchestrator. This project does not claim complete conversion to C or Java.
- Catalog cost coefficients without calibration are bootstrap priors, NOT measured latency or memory on the uploaded dataset. The optimizer does not fabricate per-dataset benchmark results.
- An uploaded dataset cannot reveal the future real operation mix by itself. The teacher must supply operation weights or genuine trace data.
- A truncated search cannot claim global optimality. The results screen shows how many combinations were actually evaluated.
- Supported file limits are 15 MB, 100000 records and 64 fields. Excel .xlsx uses its active worksheet; legacy .xls is not currently supported.

## Windows note

The new C++ reference-scan and row-browser endpoints require an updated CI-built pair of native executables. The previous downloaded binaries support the old CSV profile protocol only. After pulling this branch, download the **matching new Windows artifact** from the successful MORPHEUS CI run and replace both executables and SHA256.json under bin/windows-x64.

https://github.com/omghotekar01-dotcom/prompts---morpheus/actions/workflows/ci.yml
