# MORPHEUS Development Changelog

Record each completed development milestone with verifiable commit and test evidence. Do not infer completion from files existing or report unrun checks as passing.

| Date | Commit | Change | Tests | Status |
|---|---|---|---|---|
| 2026-11-12 | `d23f497b8a0f63048e084e816bc598e3bc69be4e` | Created `morpheus-next` from the native DSA branch and merged latest `origin/main`; retained original source refs and the pre-integration known-good tag. | Focused MWS integrity tests: 12 passed. | Branch baseline established. |
| 2026-11-12 | `0ab1851cd9377ab48970a77d9a7962b0326eb979` | Normalized CRLF in frontend source-contract checks so Windows checkouts satisfy the same exact-content assertions. | Frontend contract, TypeScript, and production build: passed. | Complete. |
| 2026-11-12 | `fbcca76d06a5b04114dce27b071894f7846028f6` | Merged BOM-safe CSV/JSON trace parsing, normalized CSV headers, and duplicate-header rejection with regression tests. | `backend/tests/test_trace_intake.py`: 17 passed. | Complete. |
| 2026-11-12 | `371de7d7cfd888604ef3af34c08cbd6c04ae35fb` | Merged stale trace-import race protection; the reference-workbench, onboarding, and readability branch content was confirmed already represented rather than merged from older trees. | Frontend contract, TypeScript, and production build: passed. | Backend full-suite and container validation remain pending. |
| 2026-11-13 | `91bf2baa3ae902e11abaa7deaed4e66c1b285a2b` | Verified and tagged the integrated baseline; PR #9 remains open for review. | Final-tree focused backend/native/XLSX/Java/trace group: 72 passed; web-hosting checks: 2 passed; C++20 CTest: 25 passed; standalone Java scorer: passed; frontend contracts, TypeScript, and production build: passed; deployment preflight: passed. The full local backend run on `0ab1851` reported 6,330 passed, 12 skipped, 6 failed: missing `openpyxl` (installed afterward), generated frontend `dist` output interfering with a test (removed; test then passed), absent local MSVC `cl.exe`, and two MinGW `.exe` path assumptions. The final-head GitHub Actions matrix passed all 11 checks, including Linux/Windows backend, MSVC, sanitizers, and guarded container smoke. | Verified; tag `morpheus-next-known-good-2026-11-13` points to this commit. Local full-suite toolchain limitations are documented; no CI checks failed. |

For future rows, include the exact commit SHA, the checks actually run (with pass/fail/skip), and any remaining limitations.
