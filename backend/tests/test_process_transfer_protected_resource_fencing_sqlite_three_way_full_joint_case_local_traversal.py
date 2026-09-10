from __future__ import annotations

from pathlib import Path

import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_case_local_literals as case_local
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint
import test_process_transfer_protected_resource_fencing_sqlite_three_way_joint_permutation_matrix as joint_matrix


def test_case_local_namespace_is_independent_of_enumeration_position() -> None:
    for sizes, start_order in full_joint.FULL_JOINT_CASES:
        expected = case_local._case_namespace(0, sizes, start_order)
        assert case_local._case_namespace(1, sizes, start_order) == expected
        assert case_local._case_namespace(5, sizes, start_order) == expected
        assert case_local._case_namespace(35, sizes, start_order) == expected


def test_full_joint_case_local_literals_under_antidiagonal_traversal(
    tmp_path: Path,
) -> None:
    """Repeat the finite 36-case oracle through an independent decomposition."""

    assert len(joint_matrix.CARDINALITY_PERMUTATIONS) == 6
    assert len(joint_matrix.START_ORDERS) == 6
    assert len(full_joint.FULL_JOINT_CASES) == 36

    original_joint_cases = joint_matrix.JOINT_CASES
    original_factory = joint_matrix.CASE_LITERAL_NAMESPACE_FACTORY
    exercised: set[tuple[tuple[int, ...], tuple[str, ...]]] = set()
    seen_namespaces: set[str] = set()
    seen_literals: set[str] = set()

    try:
        joint_matrix.CASE_LITERAL_NAMESPACE_FACTORY = case_local._case_namespace

        # E95 used start-order index (index + shift) mod 6.  This traversal uses
        # the distinct anti-diagonal family (shift - index) mod 6.  Each batch
        # is still a valid six-case orthogonal matching for the established
        # joint oracle, while all six batches cover the same 36 logical cases.
        for shift in reversed(range(6)):
            batch = tuple(
                (
                    joint_matrix.CARDINALITY_PERMUTATIONS[index],
                    joint_matrix.START_ORDERS[(shift - index) % 6],
                )
                for index in reversed(range(6))
            )
            assert len(batch) == 6
            assert len({sizes for sizes, _ in batch}) == 6
            assert len({order for _, order in batch}) == 6
            assert exercised.isdisjoint(batch)

            for sizes, start_order in batch:
                namespace = case_local._case_namespace(99, sizes, start_order)
                literals = case_local._case_literals(sizes, start_order)
                assert namespace not in seen_namespaces
                assert seen_literals.isdisjoint(literals)
                seen_namespaces.add(namespace)
                seen_literals.update(literals)

            exercised.update(batch)
            batch_path = tmp_path / f"antidiagonal-batch-{shift}"
            batch_path.mkdir()
            joint_matrix.JOINT_CASES = batch
            joint_matrix.test_three_way_dual_reconstruction_joint_permutation_matrix(
                batch_path
            )
    finally:
        joint_matrix.JOINT_CASES = original_joint_cases
        joint_matrix.CASE_LITERAL_NAMESPACE_FACTORY = original_factory

    assert exercised == set(full_joint.FULL_JOINT_CASES)
    assert len(seen_namespaces) == 36
    assert joint_matrix.JOINT_CASES is original_joint_cases
    assert joint_matrix.CASE_LITERAL_NAMESPACE_FACTORY is original_factory


def test_case_local_traversal_gate_does_not_expand_truth_claims() -> None:
    # This is bounded traversal/decomposition independence for the same finite
    # 36-case local SQLite multiprocessing model, not arbitrary scheduling,
    # fuzzing/statistical, production, performance, or novelty evidence.
    joint_matrix.test_three_way_joint_permutation_gate_does_not_expand_truth_claims()
