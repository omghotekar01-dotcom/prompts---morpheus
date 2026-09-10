from __future__ import annotations

from pathlib import Path

import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint
import test_process_transfer_protected_resource_fencing_sqlite_three_way_joint_permutation_matrix as joint_matrix


ALTERNATE_BASE_COUNTER = 91001


def test_full_joint_matrix_holds_under_alternate_literal_namespace(tmp_path: Path) -> None:
    """Re-run the finite 36-case oracle with a disjoint mutation/value namespace."""

    original_base_counter = joint_matrix.BASE_COUNTER
    assert ALTERNATE_BASE_COUNTER != original_base_counter
    assert f"mutation-{ALTERNATE_BASE_COUNTER}" != f"mutation-{original_base_counter}"
    assert f"committed-{ALTERNATE_BASE_COUNTER}" != f"committed-{original_base_counter}"

    try:
        joint_matrix.BASE_COUNTER = ALTERNATE_BASE_COUNTER
        full_joint.test_three_way_dual_reconstruction_full_joint_permutation_matrix(
            tmp_path
        )
    finally:
        joint_matrix.BASE_COUNTER = original_base_counter

    assert joint_matrix.BASE_COUNTER == original_base_counter


def test_alternate_namespace_gate_does_not_expand_truth_claims() -> None:
    # This is a second literal namespace for the same bounded finite model,
    # not arbitrary-input, fuzzing, statistical, scheduler, or production evidence.
    joint_matrix.test_three_way_joint_permutation_gate_does_not_expand_truth_claims()
