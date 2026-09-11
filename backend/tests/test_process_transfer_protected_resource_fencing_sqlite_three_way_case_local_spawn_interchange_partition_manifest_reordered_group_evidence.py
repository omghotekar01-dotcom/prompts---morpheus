from __future__ import annotations

import pytest

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_manifest as manifest_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_composition as manifested_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_group_evidence as group_evidence_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_merge_grouping as manifested_grouping_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_reordering as reordering_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


def _reordered_layouts(cases):
    for layout in reordering_gate._layouts(cases):
        yield reordering_gate._reverse_shards_and_records(layout)
        yield reordering_gate._rotate_shards_with_alternating_record_reversal(layout)


def test_reordered_manifested_shards_preserve_group_evidence_hierarchies() -> None:
    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == manifest_gate.EXPECTED_CASE_COUNT == 36

    baseline_payload = normalization_gate._normalized_export(cases)
    baseline_manifest = manifest_gate._export_manifest(baseline_payload)
    expected = manifest_gate._verify_manifest(baseline_manifest, baseline_payload)
    manifested_gate._assert_complete_derivation_invariants(expected)

    for reordered in _reordered_layouts(cases):
        flattened = tuple(case for shard in reordered for case in shard)
        assert len(flattened) == len(set(flattened)) == len(cases)
        assert set(flattened) == set(cases)

        verified_shards = manifested_grouping_gate._spawn_verified_manifested_shards(reordered)
        assert len(verified_shards) == len(reordered)

        for grouped in (
            group_evidence_gate._left_deep_manifested_merge(verified_shards, reordered),
            group_evidence_gate._balanced_manifested_merge(verified_shards, reordered),
        ):
            assert grouped == expected
            manifested_gate._assert_complete_derivation_invariants(grouped)
            final_payload = normalization_gate._normalized_export(tuple(case for case, _ in grouped))
            final_manifest = manifest_gate._export_manifest(final_payload)
            assert final_payload == baseline_payload
            assert final_manifest == baseline_manifest
            assert manifest_gate._verify_manifest(final_manifest, final_payload) == expected


def test_reordered_group_evidence_rejects_altered_intermediate_payload_and_membership() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    reordered = reordering_gate._reverse_shards_and_records((cases[:18], cases[18:]))
    declared = reordered[0]
    payload = normalization_gate._normalized_export(declared)
    group_manifest = group_evidence_gate._export_group_manifest(declared, payload)

    with pytest.raises(ValueError, match="byte length|digest"):
        group_evidence_gate._verify_group_manifest(group_manifest, declared, payload + b"\n")

    altered_declared = declared[:-1] + (reordered[1][0],)
    with pytest.raises(ValueError, match="declared logical-case|cardinality|digest"):
        group_evidence_gate._verify_group_manifest(group_manifest, altered_declared, payload)


def test_reordered_group_evidence_keeps_shard_manifest_fail_closed() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    reordered = reordering_gate._rotate_shards_with_alternating_record_reversal((cases[:18], cases[18:]))
    left_payload = normalization_gate._normalized_export(reordered[0])
    right_payload = normalization_gate._normalized_export(reordered[1])
    left_manifest = manifested_gate._export_shard_manifest(left_payload)

    assert left_payload != right_payload
    with pytest.raises(ValueError):
        manifested_gate._verify_shard_manifest(left_manifest, right_payload)


def test_reordered_group_evidence_gate_does_not_expand_truth_claims() -> None:
    # Finite local deterministic composition evidence only: two explicit
    # reorderings, two explicit hierarchy shapes, four explicit shard layouts,
    # and the established 36-case set. This is not evidence for arbitrary
    # order/topology/scheduling, distributed trust, authenticity, durability,
    # scalability, reliability, performance, production readiness, novelty,
    # patentability, or scientific effect.
    assert group_evidence_gate.GROUP_MANIFEST_SCHEMA.endswith("/v1")
