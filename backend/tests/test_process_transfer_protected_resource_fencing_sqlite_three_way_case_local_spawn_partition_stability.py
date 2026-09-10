from __future__ import annotations

import multiprocessing as mp
from queue import Empty

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_stability as spawn_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint
import test_process_transfer_protected_resource_fencing_sqlite_three_way_joint_permutation_matrix as joint_matrix


Case = spawn_gate.Case
Derived = spawn_gate.Derived
CaseDerivation = tuple[Case, Derived]


def _derive_partition(cases: tuple[Case, ...], queue: mp.Queue) -> None:
    queue.put(tuple((case, spawn_gate._derive_case(case)) for case in cases))


def _contiguous_partitions(cases: tuple[Case, ...], count: int) -> tuple[tuple[Case, ...], ...]:
    assert len(cases) % count == 0
    width = len(cases) // count
    return tuple(cases[index : index + width] for index in range(0, len(cases), width))


def _stride_partitions(cases: tuple[Case, ...], count: int) -> tuple[tuple[Case, ...], ...]:
    return tuple(cases[offset::count] for offset in range(count))


def _derive_with_spawned_partitions(
    partitions: tuple[tuple[Case, ...], ...],
) -> dict[Case, Derived]:
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [ctx.Process(target=_derive_partition, args=(partition, queue)) for partition in partitions]

    try:
        for process in processes:
            process.start()

        merged: dict[Case, Derived] = {}
        for _ in processes:
            try:
                result: tuple[CaseDerivation, ...] = queue.get(timeout=30)
            except Empty as exc:  # pragma: no cover - diagnostic failure path
                raise AssertionError("spawned partition derivation process produced no result") from exc

            for case, derived in result:
                assert case not in merged
                merged[case] = derived

        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0

        return merged
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        queue.close()
        queue.join_thread()


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


def test_case_local_derivation_is_stable_across_spawned_partitionings() -> None:
    """Compare all 36 logical derivations across distinct spawned worker decompositions."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == 36

    parent = {case: spawn_gate._derive_case(case) for case in cases}
    _assert_complete_derivation_invariants(parent)

    partitionings = (
        (cases,),
        _contiguous_partitions(cases, 2),
        _contiguous_partitions(cases, 3),
        _stride_partitions(cases, 6),
    )
    assert tuple(len(parts) for parts in partitionings) == (1, 2, 3, 6)

    for partitions in partitionings:
        flattened = tuple(case for partition in partitions for case in partition)
        assert len(flattened) == len(set(flattened)) == 36
        assert set(flattened) == set(cases)
        assert all(partition for partition in partitions)

        child = _derive_with_spawned_partitions(partitions)
        assert child == parent
        _assert_complete_derivation_invariants(child)


def test_spawn_partitioning_gate_does_not_expand_truth_claims() -> None:
    # This verifies bounded deterministic derivation equality across four
    # explicitly defined local spawned-worker decompositions of the established
    # finite 36 logical cases. It is not arbitrary scheduler/partitioning,
    # distributed-system, scalability, statistical/reliability, performance,
    # production-readiness, novelty, or scientific-effect evidence.
    joint_matrix.test_three_way_joint_permutation_gate_does_not_expand_truth_claims()
