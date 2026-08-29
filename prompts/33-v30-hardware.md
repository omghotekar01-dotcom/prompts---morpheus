# MASTER PROMPT #33 — HARDWARE-AWARE SYSTEMS OPTIMIZATION & MACHINE CALIBRATION

## Mission
Make MORPHEUS sensitive to real machine behavior without turning hardware folklore into fake precision. Physical design decisions may depend on caches, memory latency/bandwidth, branch prediction, TLB pressure, SIMD, allocators, NUMA and topology, but every hardware-aware feature must be either measured, explicitly modeled or clearly labeled as a prior/hypothesis.

## Hardware model boundary
Big-O complexity is necessary but insufficient. Two structures with similar asymptotic behavior can differ materially because of locality, pointer chasing, branch predictability, vectorization, memory amplification and update patterns. MORPHEUS therefore maintains a versioned MachineProfile and calibrated operation evidence.

## MachineProfile
Capture at minimum when available:
- OS/kernel;
- CPU model/vendor and architecture;
- logical/physical core count;
- cache hierarchy and cache-line size;
- total RAM;
- compiler/toolchain identity;
- process architecture;
- relevant frequency/governor/turbo metadata if reliably available;
- NUMA topology if relevant;
- benchmark protocol version.

The machine profile must be hashable and carried into evidence packages. Missing hardware fields remain `unknown`; never invent them.

## Cache behavior
Model and investigate:
- working-set size relative to L1/L2/L3;
- contiguous versus pointer-heavy traversal;
- cache-line utilization;
- metadata amplification;
- hot/cold access distributions;
- secondary-index fan-out;
- rebuild/migration working set.

Microbenchmarks should include scale sweeps that expose cache-regime changes. Do not fit one global curve when data show regime boundaries.

## TLB and page behavior
For large structures, page footprint and random access can dominate. Record page size where available. Evaluate huge pages only as an explicit experiment; do not assume they help. Memory-mapped/persistent formats must separately model page faults and cold-start behavior.

## Branch prediction
Hash probing, tree traversal, filters and compression codecs may respond differently to branch predictability. Prefer measured branch/CPU counters when available. If counters are unavailable, do not infer exact misprediction rates from latency alone.

## SIMD and vectorization
Expose SIMD as an implementation capability, not a universal guarantee. Candidate parameters may include scalar/SSE/AVX/AVX2/AVX-512/NEON variants only when the binary can detect/require the appropriate ISA. Generated artifacts must record required ISA and provide a safe fallback or fail closed.

## Prefetch
Manual prefetching requires evidence because it can waste bandwidth or hurt small workloads. Treat prefetch distance as a bounded parameter and benchmark it over relevant access distributions. Hardware prefetch behavior is machine-dependent.

## Memory bandwidth and latency
Separate bandwidth-bound scans from latency-bound random lookups. When practical, calibrate sequential copy/scan bandwidth and pointer/random latency proxies. Use them as interpretable features, not as magic predictors.

## Allocators
Record allocator identity if custom allocators are used. Measure allocation-heavy build/update paths separately. Arena/slab/pool allocators may improve locality but change memory accounting and lifecycle semantics. Memory metrics must include or explicitly exclude allocator reserve/slack.

## NUMA
NUMA-aware optimization is a later advanced capability. If enabled, record node topology, thread pinning, memory placement and cross-node access policy. Never compare pinned and unpinned runs as equivalent. A single-socket CI machine does not validate NUMA claims.

## Thread affinity and frequency stability
Performance campaigns should document whether threads are pinned, whether turbo/frequency scaling is controlled and whether competing load is minimized. CI smoke benchmarks are correctness/protocol checks, not publication-grade performance campaigns.

## PMU/perf counters
Optional hardware counters may include cycles, instructions, cache references/misses, branches/misses, LLC load misses and page faults. Counter availability/permission varies by OS. A missing counter must not fail core synthesis unless the model explicitly requires it.

## Hardware-aware cost features
Potential cost-model inputs:
- N / bytes / key width / value width;
- cardinality/selectivity;
- access distribution/skew;
- expected probe length/fanout/depth;
- bytes touched per operation;
- predicted/random memory accesses;
- contiguous scan length;
- implementation parameterization;
- machine cache/RAM features;
- measured primitive anchors.

Use simple interpretable models first. Validate absolute error and ranking separately. Preserve uncertainty and out-of-distribution indicators.

## Active calibration
When model uncertainty is high or candidates are close, MORPHEUS may benchmark selected primitive/candidate cells to reduce uncertainty. Active measurement selection must be deterministic/reproducible for a fixed seed/config and must not silently use the final held-out evaluation set.

## Cross-machine generalization
Machine-local calibration remains machine-local unless transfer is evaluated. Possible research directions:
- normalized features;
- hardware embedding/profile features;
- transfer calibration with a small target-machine sample;
- hierarchical models.

Report cross-machine error and ranking separately. Never claim portable prediction accuracy from one machine.

## Cold vs warm cache
Where relevant, define cache state precisely. Warm-cache runs, controlled cold-start runs and mixed production-like runs answer different questions. OS-level cache dropping may require privileges and can distort methodology; document exact procedure.

## Benchmark protocol
For each campaign freeze:
- source commit;
- machine profile hash;
- compiler/flags;
- workload/spec hash;
- record counts;
- distributions and parameters;
- operation counts;
- warmups/repetitions;
- seeds;
- affinity/frequency policy;
- raw output hashes.

## Candidate hardware score
Do not create a single opaque "hardware score". Preserve raw predicted/measured metrics and then apply the declared objective. Hardware features influence estimators, not truth labels.

## Acceptance gates
- MachineProfile is versioned and hashable;
- exact machine identity is carried into calibration/release evidence;
- calibration covers multiple sizes/distributions where claimed;
- no extrapolation is silently promoted to measured evidence;
- hardware counters are optional and provenance-aware;
- publication-grade claims do not use CI smoke measurements as final evidence;
- cross-machine claims require actual multi-machine experiments.

## Research opportunities
Evaluate cache-regime-aware models, active benchmarking efficiency, transfer calibration, uncertainty calibration, topology-aware composition and hardware-dependent primitive crossover points. Frame these as hypotheses until experiments support them.

## Truth boundary
Hardware-aware optimization is empirical systems work. MORPHEUS may model and measure hardware effects, but it cannot guarantee the globally fastest structure on every unseen machine/workload without corresponding evidence.