# MORPHEUS Calibration Protocol v2

## Status
`IMPLEMENTED / REPEATED LOCAL MEASUREMENT`, still **not publication-grade benchmarking**.

The `morpheus_calibrate` executable is MORPHEUS's target-machine primitive measurement boundary. Version 2 upgrades the original smoke harness from one aggregate timing into repeated measurements with warm-up, raw samples, median/mean/standard deviation/min/max, a deterministic seed, anti-dead-code-elimination checksum, compiler provenance and multiple operation families.

## Run
After building `core/`:

```bash
./morpheus_calibrate \
  --n 10000 \
  --ops 50000 \
  --seed 1337 \
  --repetitions 7 \
  --warmup 1
```

The JSON output can be sent to the control plane's calibration import endpoint and then explicitly activated. Importing a measurement artifact never silently changes synthesis behavior.

## Operations currently measured
The v2 harness measures a useful first matrix over real P2 implementations:

| Primitive | Build | Point | Range | Filter | Prefix | Update |
|---|---:|---:|---:|---:|---:|---:|
| Robin Hood hash | yes | yes | — | — | — | yes |
| Ordered tree | yes | yes | yes | — | — | yes |
| Sorted array | yes | yes | yes | — | — | yes |
| Bitmap/posting filter | yes | — | — | yes | — | — |
| Radix/prefix trie | yes | yes | — | — | yes | — |

This matrix is intentionally narrower than the final primitive ecosystem. Missing cells are unsupported evidence, not zeros.

## Measurement semantics
For each operation the harness records:

- `ns_per_op`: median nanoseconds per logical operation;
- `mean_ns`;
- `median_ns`;
- `stdev_ns`;
- `min_ns` / `max_ns`;
- `samples_ns`: every timed repetition;
- `repetitions`;
- workload size and operation count at the profile level;
- deterministic seed;
- compiler identity and `__cplusplus` value;
- checksum accumulated from operation outputs/state.

Build time is divided by records built. Lookup/update/range/filter/prefix timings are divided by operations executed. Range/filter/prefix include result materialization performed by the current primitive API; that behavior is part of this protocol and must remain consistent when comparing candidates.

## Evidence labels
`MEASURED_LOCAL_PROCESS_REPEATED` means exactly this: repeated wall-clock timing of current MORPHEUS primitive implementations in one local process on one machine/toolchain.

It does **not** mean:

- p50/p95/p99 request latency of a deployed service;
- cross-machine stability;
- a calibrated composite data-structure model for unsupported operations;
- end-to-end generated-artifact performance;
- superiority over external baselines;
- publication-grade statistics;
- production SLO evidence.

When an imported profile is active, the backend may use supported measurements as anchors. Candidate output remains `CALIBRATED_MODEL_NOT_END_TO_END_MEASURED` until the selected generated configuration itself is benchmarked.

## CI policy
CI runs a deliberately tiny smoke configuration with three repetitions and no warm-up. Those values verify build/execution/JSON production only. **CI timing numbers must never be copied into a paper, demo claim, patent argument or marketing statement.**

## Remaining P5 research upgrades
Before MORPHEUS can claim research-grade calibrated performance modeling, implement all of the following:

1. CPU model, core topology, cache hierarchy, RAM, OS/kernel, power/governor and frequency metadata.
2. CPU affinity/pinning and controlled background-load protocol.
3. cold-cache vs warm-cache modes.
4. multiple dataset sizes spanning in-cache to memory-bound regimes.
5. hit/miss ratios, skew/Zipf distributions, key widths and payload widths.
6. richer selectivity matrix for range/filter operations.
7. insert/delete/mixed-update workloads and dynamic-size traces.
8. allocation and memory-footprint measurement using a defined metric.
9. external baselines (`std::unordered_map`, `std::map`, sorted vector plus appropriate specialist libraries where licensing allows).
10. training/calibration split separated from held-out model evaluation.
11. ranking quality (Spearman/Kendall/top-k regret) separately from absolute prediction error.
12. bootstrap confidence intervals and effect sizes for final comparisons.
13. raw-result manifests keyed by source, compiler, machine, workload and protocol hashes.
14. scripts that fit/update model parameters from raw evidence without manually editing the primitive catalog.
15. reproducible plots/tables generated from immutable experiment artifacts.

## Truth rule
A faster number is not a result until MORPHEUS can answer: **what was measured, on which machine, under which workload, using which version, with how many samples, compared against what, and can another evaluator reproduce it?**
