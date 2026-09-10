from __future__ import annotations

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_merge as merge_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_stability as interchange_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_partition_stability as partition_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_stability as spawn_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


Case = spawn_gate.Case


def _reverse_shards_and_records(
    layout: tuple[tuple[Case, ...], ...],
) -> tuple[tuple[Case, ...], ...]:
    return tuple(tuple(reversed(shard)) for shard in reversed(layout))


def _rotate_shards_and_alternate_records(
    layout: tuple[tuple[Case, ...], ...],
) -> tuple[tuple[Case, ...], ...]:
    if not layout:
        return layout

    rotated = layout[1:] + layout[:1]
    return tuple(
        tuple(reversed(shard)) if index % 2 else shard
        for index, shard in enumerate(rotated)
    )


def _assert_same_complete_logical_set(
    layout: tuple[tuple[Case, ...], ...],
    expected_cases: tuple[Case, ...],
) -> None:
    flattened = tuple(case for shard in layout for case in shard)
    assert len(flattened) == len(expected_cases) == 36
    assert len(set(flattened)) == 36
    assert set(flattened) == set(expected_cases)


def test_canonical_partition_merge_is_stable_under_explicit_reorderings() -> None:
    """Two deterministic reorderings of four finite layouts preserve the same payload."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == 36

    layouts = (
        (cases,),
        (cases[:18], cases[18:]),
        (cases[::3], cases[1::3], cases[2::3]),
        tuple(cases[index::6] for index in range(6)),
    )
    transformations = (
        _reverse_shards_and_records,
        _rotate_shards_and_alternate_records,
    )

    normalized_cases = normalization_gate._normalize_cases(cases)
    expected = tuple((case, spawn_gate._derive_case(case)) for case in normalized_cases)
    baseline_payload = normalization_gate._normalized_export(cases)
    assert interchange_gate._import_cases(baseline_payload) == expected
    partition_gate._assert_complete_derivation_invariants(dict(expected))

    for layout in layouts:
        _assert_same_complete_logical_set(layout, cases)
        for transform in transformations:
            reordered = transform(layout)
            _assert_same_complete_logical_set(reordered, cases)

            merged = merge_gate._round_trip_layout(reordered)
            assert merged == expected
            partition_gate._assert_complete_derivation_invariants(dict(merged))

            merged_payload = normalization_gate._normalized_export(
                tuple(case for case, _ in merged)
            )
            assert merged_payload == baseline_payload
            assert interchange_gate._import_cases(merged_payload) == expected


def test_partition_merge_reordering_gate_retains_fail_closed_boundaries() -> None:
    """The stronger ordering composition must not weaken duplicate/missing rejection."""

    merge_gate.test_partition_merge_rejects_duplicate_logical_case()
    merge_gate.test_partition_merge_rejects_missing_logical_case()


def test_partition_merge_reordering_gate_does_not_expand_truth_claims() -> None:
    # This is bounded local deterministic evidence for two explicit reorderings
    # of four explicit shard layouts over the established finite 36-case set.
    # It is not evidence for arbitrary scheduling/order invariance, distributed
    # execution, durability, scalability, reliability, performance, production
    # readiness, novelty, patentability, or scientific effect.
    merge_gate.test_partition_merge_gate_does_not_expand_truth_claims()
