from __future__ import annotations

import itertools
from pathlib import Path

import test_process_transfer_protected_resource_fencing_sqlite_three_way_joint_permutation_matrix as joint_matrix


FULL_JOINT_CASES = tuple(
    itertools.product(
        joint_matrix.CARDINALITY_PERMUTATIONS,
        joint_matrix.START_ORDERS,
    )
)


def test_three_way_dual_reconstruction_full_joint_permutation_matrix(tmp_path: Path) -> None:
    """Exercise every established cardinality/start-order pair without widening the model."""

    assert len(joint_matrix.CARDINALITY_PERMUTATIONS) == 6
    assert len(joint_matrix.START_ORDERS) == 6
    assert len(FULL_JOINT_CASES) == 36
    assert len(set(FULL_JOINT_CASES)) == 36

    original_joint_cases = joint_matrix.JOINT_CASES
    exercised: set[tuple[tuple[int, ...], tuple[str, ...]]] = set()

    try:
        # Decompose the 6x6 Cartesian product into six orthogonal six-case
        # matchings. The already-verified E94 oracle requires each invocation
        # to contain every cardinality permutation and every startup order
        # exactly once; cyclic shifts satisfy that contract while covering all
        # 36 pairs exactly once across this test.
        for shift in range(6):
            batch = tuple(
                (
                    joint_matrix.CARDINALITY_PERMUTATIONS[index],
                    joint_matrix.START_ORDERS[(index + shift) % 6],
                )
                for index in range(6)
            )
            assert len(batch) == 6
            assert len({sizes for sizes, _ in batch}) == 6
            assert len({order for _, order in batch}) == 6
            assert exercised.isdisjoint(batch)
            exercised.update(batch)

            batch_path = tmp_path / f"orthogonal-batch-{shift}"
            batch_path.mkdir()
            joint_matrix.JOINT_CASES = batch
            joint_matrix.test_three_way_dual_reconstruction_joint_permutation_matrix(
                batch_path
            )
    finally:
        joint_matrix.JOINT_CASES = original_joint_cases

    assert exercised == set(FULL_JOINT_CASES)


def test_full_joint_permutation_gate_does_not_expand_truth_claims() -> None:
    joint_matrix.test_three_way_joint_permutation_gate_does_not_expand_truth_claims()
