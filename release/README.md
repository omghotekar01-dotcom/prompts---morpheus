# MORPHEUS P11 Release Package

This directory turns P10 evidence into a release that can fail closed when public claims outrun repository evidence.

## Build a release manifest

Prepare a JSON input containing a version, exact 40-character commit SHA, content-addressed artifact references, and requested claims. Then run:

```bash
python release/build_release_manifest.py release-input.json --output release-manifest.json
```

Exit codes:
- `0`: every requested claim satisfied its evidence-role gate;
- `2`: malformed input;
- `3`: manifest generated, but at least one claim is blocked by missing evidence.

A blocked manifest is useful output. It tells the team exactly which evidence must exist before a claim can be shipped.

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

The gate is intentionally conservative. Adding a hash with the right role name is not enough scientifically; the artifact itself must be valid and generated under the frozen protocol. The gate prevents obvious evidence omissions, while peer review/security/legal review remain separate responsibilities.

## P11 package documents
- `docs/PAPER-DRAFT.md` — paper structure with unfilled quantitative result slots;
- `docs/PATENT-TECHNICAL-DISCLOSURE.md` — technical disclosure, explicitly not a patentability opinion;
- `docs/STARTUP-PILOT-PLAN.md` — bounded evidence-first pilot path;
- `research/EXPERIMENT-PROTOCOL.md` — frozen P10 RQs, matrix, statistics and claim gates;
- `research/NEGATIVE-RESULTS.md` — persistent negative-results ledger.

## Release truth rule
A release is not “complete” because code builds. P11 completion requires a reproducible demo, validated P10 evidence, production-hardening decisions, documentation, and claim review. `runtime_hot_swap`, strong comparative performance claims and state-of-the-art language remain blocked until their explicit evidence roles are satisfied.
