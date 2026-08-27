# MORPHEUS P11 Release Package

This directory turns P10/P11 evidence into a release package that fails closed when public claims outrun the artifacts actually supplied.

## Release truth model

There are now three distinct checks:

1. **byte identity** — the packaged file must match its declared SHA-256;
2. **structural evidence validation** — known MORPHEUS evidence roles must satisfy their declared schema/protocol and locally decidable invariants;
3. **claim-role completeness** — a requested public claim is allowed only when the required evidence roles are present as actual release artifacts.

A claim cannot authorize itself by merely listing role names. The v2 release manifest derives claim evidence from the manifest's real artifact-role set.

These checks still do **not** prove scientific validity, novelty, patentability, independent reproducibility, security certification, customer acceptance or universal superiority.

## Build a release manifest only

Prepare JSON containing a version, exact 40-character commit SHA, content-addressed artifact references and requested claims. Then run:

```bash
python release/build_release_manifest.py release-input.json --output release-manifest.json
```

Exit codes:

- `0`: every requested claim satisfied its artifact-role gate;
- `2`: malformed input;
- `3`: manifest generated, but at least one claim is blocked by missing evidence.

The generated schema is `morpheus-release-manifest-v2`.

## Build the complete deterministic evidence package

For the stronger path, provide a descriptor where each artifact includes:

- `role`;
- local `path`;
- exact `sha256`;
- release `version` and source `commit`;
- requested `claims`.

Run:

```bash
python -m release.evidence_package release-descriptor.json \
  --output-dir dist/morpheus-evidence \
  --zip dist/morpheus-evidence.zip
```

The package builder:

- re-hashes every source file;
- rejects declared hash mismatch;
- validates known evidence structures;
- checks locally decidable cross-artifact hash links;
- constructs the claim gate from artifacts that actually exist;
- emits `release-manifest.json`;
- emits `evidence-index.json` with structural-validation results;
- copies byte-identical evidence files;
- can emit a deterministic ZIP with fixed member timestamps and ordering.

The deterministic ZIP is useful for reproducible handoff/review. It is not a cryptographic signature or third-party attestation.

## Claim classes currently enforced

- generated C++20 artifact;
- compile acceptance;
- supported-route correctness;
- measured speedup;
- beam search quality;
- calibration benefit;
- runtime adaptation benefit;
- live hot swap;
- state-of-the-art comparison.

For example, `measured_speedup` requires actual artifacts with roles:

- `experiment_manifest`;
- `raw_measurements`;
- `statistical_summary`;
- `machine_profile`;
- `baseline_manifest`.

A `state_of_art` claim additionally requires contemporary external-baseline and prior-art evidence. Standard-library smoke comparisons do not satisfy that stronger scientific meaning by themselves.

## P11 package documents

- `docs/PAPER-DRAFT.md` — paper structure with quantitative slots that must be filled from validated evidence;
- `docs/PATENT-TECHNICAL-DISCLOSURE.md` — technical disclosure, explicitly not a patentability opinion;
- `docs/STARTUP-PILOT-PLAN.md` — bounded evidence-first pilot path;
- `docs/RESEARCH-RADAR.md` — prior-art and research-boundary map;
- `research/EXPERIMENT-PROTOCOL.md` — frozen P10 RQs, matrix, statistics and claim gates;
- `research/NEGATIVE-RESULTS.md` — persistent negative-results ledger;
- `benchmark/run_baseline_matrix.py` — paired standard-library baseline evidence generator.

## Release completion rule

A release is not complete merely because code builds. Repository engineering completion, research evidence, legal/IP review and external deployment are separate dimensions.

MORPHEUS may report its deterministic repository engineering-gate percentage, but must continue to block unsupported claims such as native cross-process hot swap, universal performance superiority, patent status, publication acceptance or production customer validation until the corresponding real-world evidence exists.
