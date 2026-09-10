from __future__ import annotations

from pathlib import Path

import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint
import test_process_transfer_protected_resource_fencing_sqlite_three_way_joint_permutation_matrix as joint_matrix


def test_three_way_full_joint_matrix_repeatable_under_reversed_enumeration(
    tmp_path: Path,
) -> None:
    """Re-run the complete finite matrix on fresh states in a different order."""

    expected = set(full_joint.FULL_JOINT_CASES)
    assert len(expected) == 36

    original_joint_cases = joint_matrix.JOINT_CASES
    exercised: set[tuple[tuple[int, ...], tuple[str, ...]]] = set()

    try:
        # Use the same six orthogonal matchings as E95, but traverse both the
        # matchings and their members in reverse. This changes deterministic
        # enumeration order without widening the model or requiring any
        # particular logical mutation to win a race.
        for shift in reversed(range(6)):
            batch = tuple(
                reversed(
                    tuple(
                        (
                            joint_matrix.CARDINALITY_PERMUTATIONS[index],
                            joint_matrix.START_ORDERS[(index + shift) % 6],
                        )
                        for index in range(6)
                    )
                )
            )

            assert len(batch) == 6
            assert len({sizes for sizes, _ in batch}) == 6
            assert len({order for _, order in batch}) == 6
            assert exercised.isdisjoint(batch)
            exercised.update(batch)

            batch_path = tmp_path / f"reverse-orthogonal-batch-{shift}"
            batch_path.mkdir()
            joint_matrix.JOINT_CASES = batch
            joint_matrix.test_three_way_dual_reconstruction_joint_permutation_matrix(
                batch_path
            )
    finally:
        joint_matrix.JOINT_CASES = original_joint_cases

    assert exercised == expected


def test_full_joint_repeatability_gate_does_not_expand_truth_claims() -> None:
    # Reuse the source truth-boundary assertions from the established oracle.
    joint_matrix.test_three_way_joint_permutation_gate_does_not_expand_truth_claims()
