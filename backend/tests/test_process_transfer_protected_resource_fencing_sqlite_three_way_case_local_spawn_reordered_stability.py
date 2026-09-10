from __future__ import annotations

import multiprocessing as mp
from queue import Empty

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_stability as spawn_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint
import test_process_transfer_protected_resource_fencing_sqlite_three_way_joint_permutation_matrix as joint_matrix


Case = spawn_gate.Case
Derived = spawn_gate.Derived
CaseDerivation = tuple[Case, Derived]


def _derive_cases(cases: tuple[Case, ...], queue: mp.Queue) -> None:
    queue.put(tuple((case, spawn_gate._derive_case(case)) for case in cases))


def _assert_complete_derivation_invariants(derivations: dict[Case, Derived]) -> None:
    assert len(derivations) == 36

    namespaces = [namespace for namespace, _ in derivations.values()]
    assert len(namespaces) == len(set(namespaces)) == 36

    seen_literals: set[str] = set()
    for _, literals in derivations.values():
        literal_set = set(literals)
        assert len(literal_set) == len(literals)
        assert seen_literals.isdisjoint(literal_set)
        seen_literals.update(literal_set)


def test_case_local_derivation_is_spawn_stable_under_independent_reordering() -> None:
    """Compare logical-case derivations across independently reordered spawn inputs."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == 36

    parent = {case: spawn_gate._derive_case(case) for case in cases}
    _assert_complete_derivation_invariants(parent)

    reversed_cases = tuple(reversed(cases))
    stride_cases = cases[::2] + cases[1::2]
    assert set(reversed_cases) == set(stride_cases) == set(cases)
    assert reversed_cases != cases
    assert stride_cases != cases
    assert stride_cases != reversed_cases

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(target=_derive_cases, args=(reversed_cases, queue)),
        ctx.Process(target=_derive_cases, args=(stride_cases, queue)),
    ]

    try:
        for process in processes:
            process.start()

        child_results: list[tuple[CaseDerivation, ...]] = []
        for _ in processes:
            try:
                child_results.append(queue.get(timeout=30))
            except Empty as exc:  # pragma: no cover - diagnostic failure path
                raise AssertionError("spawned reordered derivation process produced no result") from exc

        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0

        for child_result in child_results:
            child = dict(child_result)
            assert len(child) == 36
            assert child == parent
            _assert_complete_derivation_invariants(child)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        queue.close()
        queue.join_thread()


def test_spawn_reordering_gate_does_not_expand_truth_claims() -> None:
    # This composes bounded logical-case enumeration independence with bounded
    # deterministic derivation stability across fresh local spawned interpreters.
    # It is not scheduler-neutrality, distributed-system, portability,
    # statistical/reliability, performance, production-readiness, novelty, or
    # scientific-effect evidence.
    joint_matrix.test_three_way_joint_permutation_gate_does_not_expand_truth_claims()
