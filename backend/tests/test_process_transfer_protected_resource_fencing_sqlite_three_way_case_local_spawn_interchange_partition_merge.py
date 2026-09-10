from __future__ import annotations

import multiprocessing as mp
from queue import Empty

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_stability as interchange_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_partition_stability as partition_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_stability as spawn_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


Case = spawn_gate.Case
Derived = spawn_gate.Derived
Record = tuple[Case, Derived]


def _spawn_shard_round_trip(shard_index: int, cases: tuple[Case, ...], queue: mp.Queue) -> None:
    payload = normalization_gate._normalized_export(cases)
    queue.put((shard_index, interchange_gate._import_cases(payload)))


def _merge_complete_shards(
    shards: tuple[tuple[Record, ...], ...],
    expected_cases: tuple[Case, ...],
) -> tuple[Record, ...]:
    expected_set = set(expected_cases)
    seen: dict[Case, Derived] = {}

    for shard in shards:
        for case, derived in shard:
            if case in seen:
                raise ValueError("partition merge contains a duplicate logical case")
            seen[case] = derived

    if set(seen) != expected_set:
        raise ValueError("partition merge does not contain the complete logical case set")

    ordered_cases = normalization_gate._normalize_cases(tuple(seen))
    return tuple((case, seen[case]) for case in ordered_cases)


def _round_trip_layout(layout: tuple[tuple[Case, ...], ...]) -> tuple[Record, ...]:
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(target=_spawn_shard_round_trip, args=(index, shard, queue))
        for index, shard in enumerate(layout)
    ]

    try:
        for process in processes:
            process.start()

        indexed_results: list[tuple[int, tuple[Record, ...]]] = []
        for _ in processes:
            try:
                indexed_results.append(queue.get(timeout=30))
            except Empty as exc:  # pragma: no cover - diagnostic failure path
                raise AssertionError("spawned interchange shard produced no result") from exc

        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0

        indexed_results.sort(key=lambda item: item[0])
        return _merge_complete_shards(
            tuple(records for _, records in indexed_results),
            tuple(full_joint.FULL_JOINT_CASES),
        )
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        queue.close()
        queue.join_thread()


def test_canonical_interchange_partition_merge_matches_single_shot_export() -> None:
    """Explicit shard layouts must reconstruct the same finite normalized logical set."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == 36

    layouts = (
        (cases,),
        (cases[:18], cases[18:]),
        (cases[::3], cases[1::3], cases[2::3]),
        tuple(cases[index::6] for index in range(6)),
    )
    assert all(
        len(tuple(case for shard in layout for case in shard)) == 36
        and set(case for shard in layout for case in shard) == set(cases)
        for layout in layouts
    )

    normalized_cases = normalization_gate._normalize_cases(cases)
    expected = tuple((case, spawn_gate._derive_case(case)) for case in normalized_cases)
    baseline_payload = normalization_gate._normalized_export(cases)
    assert interchange_gate._import_cases(baseline_payload) == expected
    partition_gate._assert_complete_derivation_invariants(dict(expected))

    for layout in layouts:
        merged = _round_trip_layout(layout)
        assert merged == expected
        partition_gate._assert_complete_derivation_invariants(dict(merged))
        merged_payload = normalization_gate._normalized_export(tuple(case for case, _ in merged))
        assert merged_payload == baseline_payload
        assert interchange_gate._import_cases(merged_payload) == expected


def test_partition_merge_rejects_duplicate_logical_case() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    records = tuple((case, spawn_gate._derive_case(case)) for case in cases)
    shards = (records[:18], records[18:] + (records[0],))

    try:
        _merge_complete_shards(shards, cases)
    except ValueError as exc:
        assert "duplicate logical case" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("duplicate logical case unexpectedly merged")


def test_partition_merge_rejects_missing_logical_case() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    records = tuple((case, spawn_gate._derive_case(case)) for case in cases)

    try:
        _merge_complete_shards((records[:-1],), cases)
    except ValueError as exc:
        assert "complete logical case set" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("incomplete logical case set unexpectedly merged")


def test_partition_merge_gate_does_not_expand_truth_claims() -> None:
    # This is bounded local deterministic partition/merge evidence for four
    # explicit shard layouts over the established finite 36-case logical set,
    # one test interchange schema, and Python spawn workers. It is not evidence
    # for distributed execution, arbitrary sharding, durability, scalability,
    # reliability, performance, production readiness, novelty, or scientific effect.
    normalization_gate.test_normalized_interchange_gate_does_not_expand_truth_claims()
