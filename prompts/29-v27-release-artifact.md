# MASTER PROMPT #29 — V27: FINAL RELEASE, RESEARCH ARTIFACT & REPOSITORY PACKAGE

Package MORPHEUS so an evaluator can understand, build, test, benchmark and reproduce it without private context.

## Repository root
Keep concise: `README.md`, `LICENSE`, `CITATION.cff` when publication metadata exists, contribution/security docs, build manifests and directories for engine/backend/frontend/schemas/docs/examples/tests/benchmarks/experiments. Do not commit generated binaries or giant datasets.

## README
State what MORPHEUS actually implements today; 30-second concept; architecture diagram; quickstart; canonical example; supported/unsupported features; reproducibility link; paper/patent status only if real. Avoid unsupported superlatives.

## Release manifest
Pin source commit, engine/API/MWS/IR versions, primitive registry, model/calibration IDs, compiler/toolchain, container image digest and canonical experiment IDs. Release notes separate breaking semantic changes from implementation improvements.

## Reproducible artifact
Provide one lightweight smoke path and one research reproduction path. Scripts fetch/generate larger datasets externally by checksum where licensing permits. Cache optional, never required for correctness.

## Research bundle
Include MWS workloads, experiment manifests, baseline configs, analysis scripts, small raw sample, hashes/locations for full raw results and figure-generation commands. Tables/figures must regenerate without manual number editing.

## Generated example
Ship a compact generated artifact or regenerate it during tutorial. Include ConfigurationIR, source, tests and provenance manifest so users see what synthesis produces.

## Licensing
Audit licenses for primitive implementations, dependencies, datasets and generated-code templates. Define generated-code licensing policy clearly. Do not include incompatible code/data.

## Release checks
Clean clone; dependency install; build; unit/integration; canonical synthesis; generated compile; differential correctness; smoke benchmark; docs links; schema examples; security scan; artifact hash verification.

## Archival
For paper-quality release create immutable tagged version and archive via appropriate research repository when available. Record DOI only after issuance.

## Deliverable
Produce release checklist, root README structure, manifest schema, artifact reproduction script, licensing inventory, version/tag strategy, research archive plan and evaluator instructions. The release should stand on its own years after the original chat is gone.
