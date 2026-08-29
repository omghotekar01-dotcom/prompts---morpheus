# MORPHEUS generated-candidate validation workloads

These MWS documents form a frozen **read-only** workload suite for end-to-end generated-candidate model validation. They are intentionally small enough to enumerate or benchmark repeatedly during development while still exercising different physical-design and access-locality pressures.

The suite is not claimed to represent the full distribution of production workloads. The generated-candidate benchmark uses deterministic schema-derived values and precomputes the declared access stream outside the timed region. Uniform, sequential, hotspot and finite-Zipf access are therefore measurable under the current `morpheus-access-distribution-v1` protocol. Cold-cache behavior, concurrent client contention, real trace replay, temporal phase changes and mutation-specific semantics still require separate protocols before publication claims are permitted.

| Workload | Primary pressure | Why it exists |
|---|---|---|
| `point-heavy.yaml` | uniform exact lookup | compare competing exact/ordered physical choices under dominant point traffic |
| `point-sequential.yaml` | sequential exact lookup | expose locality-sensitive behavior without confusing generator overhead with lookup latency |
| `point-hotspot.yaml` | 80/20-style hotspot exact lookup | measure a declared hot subset and test whether machine behavior changes finalist ranking |
| `point-zipf.yaml` | finite-Zipf exact lookup | exercise a reproducible long-tail skew model with explicit theta |
| `ordered-analytics.yaml` | range + point | test ordered structures and mixed exact/range tradeoffs |
| `categorical-filter.yaml` | low-cardinality filtering plus point | exercise adaptive compressed bitmap routes in a composite |
| `prefix-catalog.yaml` | prefix search plus exact lookup | exercise duplicate-preserving trie behavior alongside an exact identifier path |
| `mixed-commerce.yaml` | point + range + filter + prefix | heterogeneous composite synthesis and weighted aggregate latency |

## Distribution evidence rule

A non-uniform workload is eligible for generated-candidate measurement only when the benchmark artifact is bound to the exact semantic MWS hash, WorkloadIR hash, ConfigurationIR hash, primitive-manifest hash, record count, distribution protocol and per-query distribution parameters. MORPHEUS must reject a measurement when any of those identities differ. A uniform primitive calibration is **not** silently relabeled as hotspot/Zipf calibrated evidence; until a distribution-aware primitive calibration protocol exists, those model estimates remain high-uncertainty priors and end-to-end finalist measurements are kept separate.

## Frozen evaluation rule

For RQ2-style cost-model validation, MORPHEUS must synthesize the workload first, preserve every candidate's ConfigurationIR and primitive-manifest hashes, compile the actual generated artifact, run repeated measurements, then compare predicted aggregate query latency against the measured weighted query-route latency. A record-count override creates a new measured scale and must be reflected in the effective WorkloadIR; predicted values from a different scale must never be compared with those measurements.

At least two independently measured candidates are required before a workload contributes to ranking/oracle-hit metrics. Single-candidate workloads may still contribute implementation correctness or absolute-error evidence but cannot establish ranking quality. GitHub-hosted campaign results are exploratory reproducibility evidence only; publication claims require controlled, declared hardware under the frozen research protocol.
