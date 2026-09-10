from __future__ import annotations

import multiprocessing as mp
from queue import Empty

import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_case_local_literals as case_local
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint
import test_process_transfer_protected_resource_fencing_sqlite_three_way_joint_permutation_matrix as joint_matrix


Case = tuple[tuple[int, ...], tuple[str, ...]]
Derived = tuple[str, tuple[str, ...]]


def _derive_case(case: Case) -> Derived:
    sizes, start_order = case
    namespace = case_local._case_namespace(0, sizes, start_order)
    literals = tuple(sorted(case_local._case_literals(sizes, start_order)))
    return namespace, literals


def _derive_all_cases(queue: mp.Queue) -> None:
    queue.put(tuple(_derive_case(case) for case in full_joint.FULL_JOINT_CASES))


def test_case_local_derivation_is_stable_across_spawned_interpreters() -> None:
    """Compare all 36 case-local derivations across fresh spawned interpreters."""

    assert len(full_joint.FULL_JOINT_CASES) == 36
    expected = tuple(_derive_case(case) for case in full_joint.FULL_JOINT_CASES)

    namespaces = [namespace for namespace, _ in expected]
    assert len(namespaces) == len(set(namespaces)) == 36

    seen_literals: set[str] = set()
    for _, literals in expected:
        literal_set = set(literals)
        assert len(literal_set) == len(literals)
        assert seen_literals.isdisjoint(literal_set)
        seen_literals.update(literal_set)

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [ctx.Process(target=_derive_all_cases, args=(queue,)) for _ in range(2)]

    try:
        for process in processes:
            process.start()

        child_results = []
        for _ in processes:
            try:
                child_results.append(queue.get(timeout=30))
            except Empty as exc:  # pragma: no cover - diagnostic failure path
                raise AssertionError("spawned derivation process produced no result") from exc

        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0

        assert child_results == [expected, expected]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        queue.close()
        queue.join_thread()


def test_spawn_derivation_gate_does_not_expand_truth_claims() -> None:
    # This verifies deterministic literal derivation across two fresh local
    # spawned Python interpreters for the established finite 36 logical cases.
    # It is not distributed-system, scheduler-neutral, statistical/reliability,
    # performance, production-readiness, novelty, or scientific-effect evidence.
    joint_matrix.test_three_way_joint_permutation_gate_does_not_expand_truth_claims()
