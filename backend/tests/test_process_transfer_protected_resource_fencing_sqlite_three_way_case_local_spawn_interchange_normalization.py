from __future__ import annotations

import multiprocessing as mp
from queue import Empty

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_stability as interchange_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_partition_stability as partition_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_stability as spawn_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


Case = spawn_gate.Case


def _case_sort_key(case: Case) -> tuple[tuple[int, ...], tuple[str, ...]]:
    sizes, start_order = case
    return tuple(sizes), tuple(start_order)


def _normalize_cases(cases: tuple[Case, ...]) -> tuple[Case, ...]:
    if len(cases) != len(set(cases)):
        raise ValueError("normalized derivation interchange requires unique logical cases")
    return tuple(sorted(cases, key=_case_sort_key))


def _normalized_export(cases: tuple[Case, ...]) -> bytes:
    return interchange_gate._export_cases(_normalize_cases(cases))


def _spawn_normalized_round_trip(data: bytes, queue: mp.Queue) -> None:
    queue.put(interchange_gate._import_cases(data))


def test_case_local_interchange_normalizes_independent_record_orderings() -> None:
    """Equivalent finite logical-case sets must have one canonical byte encoding."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == 36

    reordered = (
        cases,
        tuple(reversed(cases)),
        cases[::2] + cases[1::2],
    )
    assert all(len(order) == 36 and set(order) == set(cases) for order in reordered)
    assert len({order for order in reordered}) == 3

    payloads = tuple(_normalized_export(order) for order in reordered)
    assert payloads[0] == payloads[1] == payloads[2]

    normalized_cases = _normalize_cases(cases)
    expected = tuple((case, spawn_gate._derive_case(case)) for case in normalized_cases)
    assert interchange_gate._import_cases(payloads[0]) == expected
    partition_gate._assert_complete_derivation_invariants(dict(expected))

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(target=_spawn_normalized_round_trip, args=(payload, queue))
        for payload in payloads
    ]

    try:
        for process in processes:
            process.start()

        child_results = []
        for _ in processes:
            try:
                child_results.append(queue.get(timeout=30))
            except Empty as exc:  # pragma: no cover - diagnostic failure path
                raise AssertionError("spawned normalized interchange process produced no result") from exc

        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0

        assert child_results == [expected, expected, expected]
        for child in child_results:
            partition_gate._assert_complete_derivation_invariants(dict(child))
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        queue.close()
        queue.join_thread()


def test_normalized_interchange_rejects_duplicate_logical_case() -> None:
    cases = tuple(full_joint.FULL_JOINT_CASES)
    duplicate_cases = cases + (cases[0],)

    try:
        _normalized_export(duplicate_cases)
    except ValueError as exc:
        assert "unique logical cases" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("duplicate logical case unexpectedly normalized")


def test_normalized_interchange_gate_does_not_expand_truth_claims() -> None:
    # This is bounded deterministic normalization evidence for three explicit
    # enumerations of the established finite 36-case set, one test interchange
    # schema, and local Python spawn workers. It is not arbitrary serialization
    # portability, durability, distributed execution, scheduling, reliability,
    # performance, production-readiness, novelty, or scientific-effect evidence.
    interchange_gate.test_spawn_interchange_gate_does_not_expand_truth_claims()
