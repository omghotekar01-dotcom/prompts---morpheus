# MORPHEUS generated-candidate validation workloads

These MWS documents are the first frozen **read-only** workload suite for end-to-end generated-candidate model validation. They are intentionally small enough to enumerate or benchmark repeatedly during development while still exercising different physical-design pressures.

The suite is not claimed to represent the full distribution of production workloads. The current candidate benchmark synthesizes deterministic schema-derived values; skew, temporal locality, cold-cache behavior, concurrency and mutation-specific semantics require separate protocols before publication claims are permitted.

| Workload | Primary pressure | Why it exists |
|---|---|---|
| `point-heavy.yaml` | exact lookup | compare competing exact/ordered physical choices under dominant point traffic |
| `ordered-analytics.yaml` | range + point | test ordered structures and mixed exact/range tradeoffs |
| `categorical-filter.yaml` | low-cardinality filtering plus point | exercise adaptive compressed bitmap routes in a composite |
| `prefix-catalog.yaml` | prefix search plus exact lookup | exercise duplicate-preserving trie behavior alongside an exact identifier path |
| `mixed-commerce.yaml` | point + range + filter + prefix | heterogeneous composite synthesis and weighted aggregate latency |

## Frozen evaluation rule

For RQ2-style cost-model validation, MORPHEUS must synthesize the workload first, preserve every candidate's ConfigurationIR and primitive-manifest hashes, compile the actual generated artifact, run repeated measurements, then compare predicted aggregate query latency against the measured weighted query-route latency. A record-count override creates a new measured scale and must be reflected in the effective WorkloadIR; predicted values from a different scale must never be compared with those measurements.

At least two independently measured candidates are required before a workload contributes to ranking/oracle-hit metrics. Single-candidate workloads may still contribute implementation correctness or absolute-error evidence but cannot establish ranking quality.
