# MORPHEUS Calibration Protocol v1

## Status
`SCAFFOLDED / SMOKE-MEASURED`, not publication-grade calibration.

The `morpheus_calibrate` executable is the first real measurement boundary in MORPHEUS. It measures build and point-lookup time for a small set of real P2 primitives in one local process. Its purpose is to establish a reproducible measurement contract before the P5 benchmark laboratory grows into a statistically rigorous target-machine calibration system.

## Command
After building `core/`:

```bash
./morpheus_calibrate --n 10000 --ops 50000 --seed 1337
```

The executable emits JSON containing:
- protocol identifier;
- record count;
- operation count;
- deterministic seed;
- anti-dead-code-elimination checksum;
- measured nanoseconds per operation for build and point lookup.

## What this evidence means
`MEASURED_LOCAL_PROCESS` means only that wall-clock process measurements were produced by this run. It does **not** imply:
- benchmark stability across machines;
- calibrated predictive-model accuracy;
- p99 latency;
- publication-quality results;
- performance superiority over external baselines.

## P5 upgrades still required
Before the backend may replace bootstrap priors with calibrated evidence, implement:
1. machine-profile capture (CPU, OS, compiler, flags, clock/power policy when available);
2. warm-up and multiple independent repetitions;
3. raw per-repetition storage rather than only an aggregate;
4. confidence intervals / robust summary statistics;
5. multiple sizes and key distributions;
6. range/selectivity/filter/update/delete/build measurements;
7. cache-state protocol;
8. fair standard-library and specialist baselines;
9. train/calibration vs held-out evaluation split;
10. absolute-error and ranking-quality reports;
11. calibration artifact schema with provenance hashes;
12. scripts that convert raw observations into model parameters without hand-editing values.

## CI use
CI runs only a tiny calibration smoke test to verify that the harness builds and executes. CI timing values are ephemeral and must not be copied into papers, marketing material, or the bootstrap cost catalog.