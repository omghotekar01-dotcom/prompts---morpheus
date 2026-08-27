# MORPHEUS External Specialist Baseline Policy

Standard-library comparisons are useful engineering controls, but they are not enough for a contemporary research superiority claim. P10 therefore separates **standard controls** from **specialist external baselines**.

## Baseline tiers

### Tier A — standard controls

Already implemented by `morpheus_baseline_bench` and `run_baseline_matrix.py`:

- `std::unordered_map` for exact-match hash lookup;
- `std::map` for ordered point/range lookup.

These are reproducible language-library controls, not state-of-the-art specialist baselines.

### Tier B — specialist hash tables

Candidate systems for the exact-match benchmark family include:

- Abseil `absl::flat_hash_map` / Swiss table (`https://github.com/abseil/abseil-cpp`);
- Boost.Unordered `boost::unordered_flat_map` (`https://www.boost.org/latest/libs/unordered/`);
- Folly F14 (`https://github.com/facebook/folly/blob/main/folly/container/F14.md`).

The sources describe these as optimized/open-addressing production-grade alternatives to standard unordered containers. MORPHEUS must benchmark exact pinned revisions rather than assuming any performance ordering.

### Tier C — specialist ordered/B+ trees

For in-memory ordered-index comparison, the obsolete standalone STX B+ tree must **not** be used as the current reference merely because it is historically popular. Its own repository says the maintained implementation moved into TLX. A contemporary adapter should therefore target the maintained TLX B-tree/container implementation (`https://github.com/tlx/tlx`) or another actively maintained, clearly licensed ordered-index implementation selected before the experiment freeze.

### Tier D — system-level/database baselines

A database/index-tuning paper requires system-level baselines in addition to container microbenchmarks. The exact systems, versions, physical-design knobs and workload adapters must be frozen in the experiment manifest. Container-level results must not be presented as database-system superiority.

## Mandatory fairness rules

Every external baseline run must record:

1. project identity and canonical source URL;
2. immutable commit/tag/release identifier;
3. license identifier as observed at experiment-freeze time;
4. compiler identity/version and all compile/link flags;
5. CPU/OS/memory/governor/affinity machine profile;
6. allocator and relevant runtime options;
7. data type and payload size;
8. input-key distribution and deterministic seed;
9. operation mix, selectivity and warm-up policy;
10. build/reserve/bulk-load choices;
11. repetition count and raw samples;
12. exact adapter source SHA-256;
13. semantic notes where APIs differ (pointer stability, duplicate-key rules, mutation support, range semantics);
14. failures, unsupported operations and negative results.

## No benchmark laundering

MORPHEUS must reject these shortcuts:

- comparing a release build against a debug external baseline;
- selectively reserving capacity for MORPHEUS but not a baseline when the baseline supports equivalent reservation;
- hiding baseline build cost when MORPHEUS build cost is reported;
- reporting only the workload sizes/seeds where MORPHEUS wins;
- silently dropping timeouts or failed external runs;
- treating a standard-library control as a specialist state-of-the-art baseline;
- comparing different payload/key semantics without documenting the difference;
- using CI runner timing as publication evidence;
- calling an external system “slower” without preserving raw paired samples and machine provenance.

## Artifact contract

A Tier B/C/D experiment must emit an `external_baseline_manifest` conforming to `benchmark/external_baseline_manifest.schema.json`. P11 `state_of_art` claims already require the `external_baseline_manifest` role plus prior-art, raw measurement, statistical and machine-profile evidence.

The manifest establishes **identity and reproducibility metadata**. It does not itself establish that the baseline was implemented fairly; that conclusion still depends on adapter review and the raw experiment bundle.
