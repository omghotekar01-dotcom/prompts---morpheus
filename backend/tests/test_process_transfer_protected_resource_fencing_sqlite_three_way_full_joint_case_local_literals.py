from __future__ import annotations

from pathlib import Path

import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint
import test_process_transfer_protected_resource_fencing_sqlite_three_way_joint_permutation_matrix as joint_matrix


def _case_namespace(
    case_index: int,
    sizes: tuple[int, ...],
    start_order: tuple[str, ...],
) -> str:
    # The case index is intentionally not relied on for uniqueness because the
    # full-matrix oracle invokes the six-case joint oracle in multiple batches.
    del case_index
    sizes_key = "".join(str(size) for size in sizes)
    order_key = "".join(start_order)
    return f"sizes-{sizes_key}-order-{order_key}"


def _case_literals(
    sizes: tuple[int, ...], start_order: tuple[str, ...]
) -> set[str]:
    namespace = _case_namespace(0, sizes, start_order)
    suffix = f"-{namespace}"
    pending_counter = joint_matrix.BASE_COUNTER + 1
    successor_counter = joint_matrix.BASE_COUNTER + 2

    mutation_ids = {
        f"mutation-{pending_counter}-{group}{suffix}" for group in joint_matrix.GROUPS
    }
    values = {
        f"committed-{pending_counter}-{group}{suffix}" for group in joint_matrix.GROUPS
    }
    assert len(mutation_ids) == 3
    assert len(values) == 3

    return {
        f"mutation-{joint_matrix.BASE_COUNTER}{suffix}",
        f"committed-{joint_matrix.BASE_COUNTER}{suffix}",
        *mutation_ids,
        *values,
        f"mutation-{successor_counter}-successor{suffix}",
        f"committed-{successor_counter}-successor{suffix}",
    }


def test_full_joint_matrix_uses_distinct_case_local_literal_namespaces(
    tmp_path: Path,
) -> None:
    """Exercise all 36 established cases with deterministic case-local literals."""

    assert len(full_joint.FULL_JOINT_CASES) == 36
    namespaces = [
        _case_namespace(0, sizes, start_order)
        for sizes, start_order in full_joint.FULL_JOINT_CASES
    ]
    assert len(namespaces) == len(set(namespaces)) == 36

    seen_literals: set[str] = set()
    for sizes, start_order in full_joint.FULL_JOINT_CASES:
        literals = _case_literals(sizes, start_order)
        # Every fresh-state case owns a disjoint baseline/pending/successor
        # literal namespace. This makes cross-case literal leakage observable
        # rather than silently reusing a previous case's strings.
        assert seen_literals.isdisjoint(literals)
        seen_literals.update(literals)

    original_factory = joint_matrix.CASE_LITERAL_NAMESPACE_FACTORY
    try:
        joint_matrix.CASE_LITERAL_NAMESPACE_FACTORY = _case_namespace
        full_joint.test_three_way_dual_reconstruction_full_joint_permutation_matrix(
            tmp_path
        )
    finally:
        joint_matrix.CASE_LITERAL_NAMESPACE_FACTORY = original_factory

    assert joint_matrix.CASE_LITERAL_NAMESPACE_FACTORY is original_factory


def test_case_local_literal_gate_does_not_expand_truth_claims() -> None:
    # This is bounded independence from one fixed literal namespace across the
    # already-defined 36-case model, not arbitrary-input, fuzzing, statistical,
    # scheduler-neutral, performance, production-readiness, or novelty evidence.
    joint_matrix.test_three_way_joint_permutation_gate_does_not_expand_truth_claims()
