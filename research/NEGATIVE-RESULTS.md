# MORPHEUS Negative Results Ledger

This file is append-only in spirit: failed hypotheses, regressions, portability faults and unfavorable benchmark outcomes belong in the research record. A later fix may add a resolution, but the original observation should remain visible.

## Entry template

### NR-YYYY-NNN — Short title
- **Date:** YYYY-MM-DD
- **Experiment IDs:** `mx-...`
- **Commit:** `<git sha>`
- **Machine profile:** `<artifact/hash/path>`
- **Evidence state:** `MEASURED`, `FAILED_VERIFICATION`, `BLOCKED`, etc.
- **Expected:** what the hypothesis predicted.
- **Observed:** measured or verified outcome.
- **Raw evidence:** exact artifact/sample references.
- **Likely cause:** hypothesis, clearly labelled if uncertain.
- **Decision:** keep claim / narrow claim / reject claim / redesign mechanism.
- **Resolution:** optional later follow-up with commit/experiment IDs.

## Current known engineering negatives / boundaries

### NR-2026-001 — Ordered tree is not yet a B+ tree
- **Date:** 2026-08-27
- **Evidence state:** `KNOWN_IMPLEMENTATION_BOUNDARY`
- **Observed:** `OrderedTreeIndex` is a `std::map` correctness proxy.
- **Decision:** no B+tree-specific or state-of-the-art ordered-index claims are permitted until a real implementation/baseline is integrated and measured.

### NR-2026-002 — Bitmap baseline is uncompressed
- **Date:** 2026-08-27
- **Evidence state:** `KNOWN_IMPLEMENTATION_BOUNDARY`
- **Observed:** bitmap filtering currently uses posting-vector correctness behavior rather than a compressed Roaring/WAH/EWAH-class implementation.
- **Decision:** memory/performance claims must identify it as the repository bitmap baseline.

### NR-2026-003 — Runtime hot swap is not implemented
- **Date:** 2026-08-27
- **Evidence state:** `KNOWN_IMPLEMENTATION_BOUNDARY`
- **Observed:** the runtime layer supports drift detection, hysteresis, migration gating, control-plane confirmation and rollback authorization, but not a proven concurrent process-level data-plane pointer/version swap.
- **Decision:** RQ5 may evaluate control-policy simulations/controls separately, but “live hot swap” is blocked until a real data-plane transition worker exists.

### NR-2026-004 — Publication-grade speedup evidence does not yet exist
- **Date:** 2026-08-27
- **Evidence state:** `MEASUREMENTS_NOT_YET_RUN`
- **Observed:** calibration smoke measurements and CI checks exist, but there is no frozen multi-baseline RQ1 campaign supporting a public X%-faster claim.
- **Decision:** any performance number shown before the P10 measured campaign must be labelled model prediction or local smoke measurement, never general speedup evidence.
