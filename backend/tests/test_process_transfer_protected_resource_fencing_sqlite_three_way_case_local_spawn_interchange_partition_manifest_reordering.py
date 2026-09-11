from __future__ import annotations

import pytest

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_manifest as manifest_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_composition as manifested_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


def _layouts(cases: tuple[manifested_gate.Case, ...]) -> tuple[tuple[tuple[manifested_gate.Case, ...], ...], ...]:
    return (
        (cases,),
        (cases[:18], cases[18:]),
        (cases[::3], cases[1::3], cases[2::3]),
        tuple(cases[index::6] for index in range(6)),
    )


def _reverse_shards_and_records(
    layout: tuple[tuple[manifested_gate.Case, ...], ...],
) -> tuple[tuple[manifested_gate.Case, ...], ...]:
    return tuple(tuple(reversed(shard)) for shard in reversed(layout))


def _rotate_shards_with_alternating_record_reversal(
    layout: tuple[tuple[manifested_gate.Case, ...], ...],
) -> tuple[tuple[manifested_gate.Case, ...], ...]:
    rotated = layout[1:] + layout[:1]
    return tuple(
        tuple(reversed(shard)) if index % 2 else shard
        for index, shard in enumerate(rotated)
    )


def test_manifested_shard_reorderings_preserve_final_payload_and_manifest() -> None:
    """Two explicit finite reorderings preserve the already-verified manifested merge result."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == manifest_gate.EXPECTED_CASE_COUNT == 36

    baseline_payload = normalization_gate._normalized_export(cases)
    baseline_manifest = manifest_gate._export_manifest(baseline_payload)
    expected = manifest_gate._verify_manifest(baseline_manifest, baseline_payload)
    manifested_gate._assert_complete_derivation_invariants(expected)

    for layout in _layouts(cases):
        for reordered in (
            _reverse_shards_and_records(layout),
            _rotate_shards_with_alternating_record_reversal(layout),
        ):
            flattened = tuple(case for shard in reordered for case in shard)
            assert len(flattened) == len(set(flattened)) == len(cases)
            assert set(flattened) == set(cases)

            merged = manifested_gate._round_trip_manifested_layout(reordered)
            assert merged == expected
            manifested_gate._assert_complete_derivation_invariants(merged)

            merged_payload = normalization_gate._normalized_export(tuple(case for case, _ in merged))
            merged_manifest = manifest_gate._export_manifest(merged_payload)
            assert merged_payload == baseline_payload
            assert merged_manifest == baseline_manifest
            assert manifest_gate._verify_manifest(merged_manifest, merged_payload) == expected


def test_reordered_manifested_merge_still_fails_closed_for_duplicate_and_missing_cases() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))

    duplicate_layout = (
        tuple(reversed(cases[:18])),
        tuple(reversed(cases[18:])) + (cases[0],),
    )
    with pytest.raises(ValueError):
        manifested_gate._round_trip_manifested_layout(duplicate_layout)

    missing_layout = (
        tuple(reversed(cases[:18])),
        tuple(reversed(cases[18:-1])),
    )
    with pytest.raises(ValueError):
        manifested_gate._round_trip_manifested_layout(missing_layout)


def test_reordered_manifest_boundary_rejects_payload_manifest_mismatch() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    left_payload = normalization_gate._normalized_export(tuple(reversed(cases[:18])))
    right_payload = normalization_gate._normalized_export(tuple(reversed(cases[18:])))
    left_manifest = manifested_gate._export_shard_manifest(left_payload)

    assert left_payload != right_payload
    with pytest.raises(ValueError):
        manifested_gate._verify_shard_manifest(left_manifest, right_payload)
