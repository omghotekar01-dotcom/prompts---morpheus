# MASTER PROMPT #28 — V26: WORLD-CLASS AUDIT, RED TEAM & COMPLETENESS GATE

Before publication, competition, pilot or "complete" status, audit MORPHEUS adversarially. The goal is to discover why claims could be wrong.

## Architecture audit
Trace every canonical contract through code. Flag duplicate representations, cyclic dependencies, UI/business logic in optimizer, LLM in truth path, hidden defaults, unversioned schemas and non-deterministic resolution.

## Correctness audit
Run differential/stateful/fuzz/sanitizer tests across supported operation/primitive combinations. Test composite update synchronization, empty/boundary cases, failed builds and migration/adaptation. Any correctness failure blocks performance claims for that configuration.

## Search audit
Enumerate small spaces. Verify feasibility and safe pruning. Measure heuristic regret. Search for workloads where chosen candidate is poor. Report them.

## Model audit
Evaluate held-out machines/workloads; interpolation vs extrapolation; ranking errors; uncertainty calibration; crossover regions. Ensure measured data was not used inadvertently as test/training leakage.

## Benchmark audit
Check baseline fairness, compiler flags, warmup/repetition, dead-code elimination, timer overhead, cache state, memory definition, dataset equivalence and statistical reporting. Recompute figures from raw data.

## Reproducibility audit
Fresh machine/container follows docs and regenerates canonical result from pinned inputs. Verify hashes/manifests and no hidden local files.

## Security audit
Threat-model auth, tenant isolation, parser, uploads, artifact store, queue, compiler sandbox, generated code, plugins, AI tools and telemetry. Attempt injection, traversal, SSRF, resource exhaustion and secret leakage.

## Research audit
For every sentence-level contribution/quantitative/novelty claim, link evidence. Mark IMPLEMENTED vs PROPOSED. Verify related-work/patent searches are current at publication time. Identify threats and negative results.

## Product audit
Test fresh-user onboarding, invalid workload recovery, failed synthesis, infeasible constraints, artifact integration and uninstall/cleanup. Remove fake dashboard data and dead controls.

## Storage audit
Keep Git lightweight: source/spec/docs/small fixtures only. Exclude generated binaries, huge traces, calibration dumps and duplicate exports. Use compressed external artifacts/releases when necessary and manifests in Git.

## Gate table
Rate each area PASS/BLOCKER/KNOWN-LIMITATION: specification, IR, primitives, cost, search, codegen, correctness, benchmarking, adaptation, backend, UI, AI, security, reproducibility, research, docs, demo. A blocker prevents corresponding claim/release.

## Deliverable
Produce `AUDIT.md`, blocker list, evidence matrix, claim matrix, reproducibility report, security findings, performance caveats and remediation order. Do not optimize the audit for flattering conclusions.
