from __future__ import annotations

import pytest

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_manifest as manifest_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_composition as manifested_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_merge_grouping as manifested_grouping_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_reordering as reordering_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_merge_grouping as grouping_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


def test_reordered_manifested_shards_preserve_both_hierarchical_merge_groupings() -> None:
    """The two verified finite reorderings compose with both verified merge trees."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == manifest_gate.EXPECTED_CASE_COUNT == 36

    baseline_payload = normalization_gate._normalized_export(cases)
    baseline_manifest = manifest_gate._export_manifest(baseline_payload)
    expected = manifest_gate._verify_manifest(baseline_manifest, baseline_payload)
    manifested_gate._assert_complete_derivation_invariants(expected)

    for layout in reordering_gate._layouts(cases):
        for reordered in (
            reordering_gate._reverse_shards_and_records(layout),
            reordering_gate._rotate_shards_with_alternating_record_reversal(layout),
        ):
            flattened = tuple(case for shard in reordered for case in shard)
            assert len(flattened) == len(set(flattened)) == len(cases)
            assert set(flattened) == set(cases)

            verified_shards = manifested_grouping_gate._spawn_verified_manifested_shards(reordered)
            assert len(verified_shards) == len(reordered)

            for grouped in (
                grouping_gate._left_deep_merge(verified_shards, reordered),
                grouping_gate._balanced_merge(verified_shards, reordered),
            ):
                assert grouped == expected
                manifested_gate._assert_complete_derivation_invariants(grouped)

                grouped_payload = normalization_gate._normalized_export(
                    tuple(case for case, _ in grouped)
                )
                grouped_manifest = manifest_gate._export_manifest(grouped_payload)
                assert grouped_payload == baseline_payload
                assert grouped_manifest == baseline_manifest
                assert manifest_gate._verify_manifest(grouped_manifest, grouped_payload) == expected


def test_reordered_manifested_hierarchy_rejects_intermediate_duplicate_and_missing_cases() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    layout = (cases[:18], cases[18:])
    reordered = reordering_gate._reverse_shards_and_records(layout)
    verified_left, verified_right = manifested_grouping_gate._spawn_verified_manifested_shards(reordered)
    left_cases, right_cases = reordered

    with pytest.raises(ValueError, match="duplicate logical case"):
        grouping_gate._merge_declared_groups(
            (verified_left, verified_right + (verified_left[0],)),
            (left_cases, right_cases),
        )

    with pytest.raises(ValueError, match="complete logical case set"):
        grouping_gate._merge_declared_groups(
            (verified_left[:-1], verified_right),
            (left_cases, right_cases),
        )


def test_reordered_manifested_hierarchy_rejects_payload_manifest_mismatch() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    layout = reordering_gate._rotate_shards_with_alternating_record_reversal(
        (cases[:18], cases[18:])
    )
    left_payload = normalization_gate._normalized_export(layout[0])
    right_payload = normalization_gate._normalized_export(layout[1])
    left_manifest = manifested_gate._export_shard_manifest(left_payload)

    assert left_payload != right_payload
    with pytest.raises(ValueError):
        manifested_gate._verify_shard_manifest(left_manifest, right_payload)


def test_reordered_manifested_hierarchical_grouping_gate_does_not_expand_truth_claims() -> None:
    # This is bounded local deterministic composition evidence for two explicit
    # reorderings, two explicit hierarchical merge trees, and four explicit
    # manifested shard layouts of the established finite 36-case set. It is
    # not evidence for arbitrary ordering/associativity/topology/scheduling,
    # distributed execution or trust, authenticity, durability, scalability,
    # reliability, performance, production readiness, novelty, patentability,
    # or scientific effect.
    manifested_grouping_gate.test_manifested_hierarchical_grouping_gate_does_not_expand_truth_claims()
