from __future__ import annotations

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_partition_stability as partition_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_stability as spawn_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint
import test_process_transfer_protected_resource_fencing_sqlite_three_way_joint_permutation_matrix as joint_matrix


Case = spawn_gate.Case


def _reverse_partition_and_case_order(
    partitions: tuple[tuple[Case, ...], ...],
) -> tuple[tuple[Case, ...], ...]:
    return tuple(tuple(reversed(partition)) for partition in reversed(partitions))


def _rotate_partitions_and_alternate_case_order(
    partitions: tuple[tuple[Case, ...], ...],
) -> tuple[tuple[Case, ...], ...]:
    if len(partitions) > 1:
        reordered = partitions[1:] + partitions[:1]
    else:
        reordered = partitions
    return tuple(
        tuple(reversed(partition)) if index % 2 == 0 else partition
        for index, partition in enumerate(reordered)
    )


def test_case_local_derivation_is_stable_across_partition_and_case_reordering() -> None:
    """Compose the established spawned partitioning and input-reordering dimensions."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == 36

    parent = {case: spawn_gate._derive_case(case) for case in cases}
    partition_gate._assert_complete_derivation_invariants(parent)

    base_partitionings = (
        (cases,),
        partition_gate._contiguous_partitions(cases, 2),
        partition_gate._contiguous_partitions(cases, 3),
        partition_gate._stride_partitions(cases, 6),
    )
    assert tuple(len(parts) for parts in base_partitionings) == (1, 2, 3, 6)

    reorderings = (
        _reverse_partition_and_case_order,
        _rotate_partitions_and_alternate_case_order,
    )

    for base_partitions in base_partitionings:
        for reorder in reorderings:
            partitions = reorder(base_partitions)
            flattened = tuple(case for partition in partitions for case in partition)

            assert len(partitions) == len(base_partitions)
            assert all(partition for partition in partitions)
            assert len(flattened) == len(set(flattened)) == 36
            assert set(flattened) == set(cases)
            assert flattened != tuple(case for partition in base_partitions for case in partition)

            child = partition_gate._derive_with_spawned_partitions(partitions)
            assert child == parent
            partition_gate._assert_complete_derivation_invariants(child)


def test_spawn_partition_reordering_gate_does_not_expand_truth_claims() -> None:
    # This verifies bounded deterministic derivation equality across two explicit
    # reorderings of four explicit local spawned-worker decompositions of the
    # established finite 36 logical cases. It is not arbitrary scheduling or
    # partitioning, distributed execution, scalability, statistical/reliability,
    # performance, production-readiness, novelty, or scientific-effect evidence.
    joint_matrix.test_three_way_joint_permutation_gate_does_not_expand_truth_claims()
