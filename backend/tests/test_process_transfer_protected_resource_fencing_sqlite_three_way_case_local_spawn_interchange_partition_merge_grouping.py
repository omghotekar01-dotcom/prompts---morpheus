from __future__ import annotations

import multiprocessing as mp
from queue import Empty

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_merge as merge_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_stability as interchange_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_partition_stability as partition_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_stability as spawn_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


Case = spawn_gate.Case
Record = merge_gate.Record


def _round_trip_shards(layout: tuple[tuple[Case, ...], ...]) -> tuple[tuple[Record, ...], ...]:
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(target=merge_gate._spawn_shard_round_trip, args=(index, shard, queue))
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
        return tuple(records for _, records in indexed_results)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        queue.close()
        queue.join_thread()


def _merge_declared_groups(
    record_groups: tuple[tuple[Record, ...], ...],
    case_groups: tuple[tuple[Case, ...], ...],
) -> tuple[Record, ...]:
    assert len(record_groups) == len(case_groups)
    expected_cases = tuple(case for group in case_groups for case in group)
    return merge_gate._merge_complete_shards(record_groups, expected_cases)


def _left_deep_merge(
    shards: tuple[tuple[Record, ...], ...],
    layout: tuple[tuple[Case, ...], ...],
) -> tuple[Record, ...]:
    merged = shards[0]
    expected = layout[0]
    for shard, cases in zip(shards[1:], layout[1:]):
        merged = _merge_declared_groups((merged, shard), (expected, cases))
        expected = expected + cases
    return merged


def _balanced_merge(
    shards: tuple[tuple[Record, ...], ...],
    layout: tuple[tuple[Case, ...], ...],
) -> tuple[Record, ...]:
    record_groups = list(shards)
    case_groups = list(layout)
    while len(record_groups) > 1:
        next_records: list[tuple[Record, ...]] = []
        next_cases: list[tuple[Case, ...]] = []
        for index in range(0, len(record_groups), 2):
            if index + 1 == len(record_groups):
                next_records.append(record_groups[index])
                next_cases.append(case_groups[index])
                continue
            next_records.append(
                _merge_declared_groups(
                    (record_groups[index], record_groups[index + 1]),
                    (case_groups[index], case_groups[index + 1]),
                )
            )
            next_cases.append(case_groups[index] + case_groups[index + 1])
        record_groups = next_records
        case_groups = next_cases
    return record_groups[0]


def test_canonical_partition_merge_is_stable_under_explicit_grouping_trees() -> None:
    """Two finite hierarchical merge trees preserve one canonical 36-case payload."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == 36

    layouts = (
        (cases,),
        (cases[:18], cases[18:]),
        (cases[::3], cases[1::3], cases[2::3]),
        tuple(cases[index::6] for index in range(6)),
    )

    normalized_cases = normalization_gate._normalize_cases(cases)
    expected = tuple((case, spawn_gate._derive_case(case)) for case in normalized_cases)
    baseline_payload = normalization_gate._normalized_export(cases)
    assert interchange_gate._import_cases(baseline_payload) == expected
    partition_gate._assert_complete_derivation_invariants(dict(expected))

    for layout in layouts:
        flattened = tuple(case for shard in layout for case in shard)
        assert len(flattened) == len(set(flattened)) == 36
        assert set(flattened) == set(cases)

        reconstructed = _round_trip_shards(layout)
        assert len(reconstructed) == len(layout)

        for grouped in (
            _left_deep_merge(reconstructed, layout),
            _balanced_merge(reconstructed, layout),
        ):
            assert grouped == expected
            partition_gate._assert_complete_derivation_invariants(dict(grouped))
            grouped_payload = normalization_gate._normalized_export(
                tuple(case for case, _ in grouped)
            )
            assert grouped_payload == baseline_payload
            assert interchange_gate._import_cases(grouped_payload) == expected


def test_hierarchical_merge_rejects_intermediate_duplicate_and_missing_cases() -> None:
    """Declared intermediate case sets retain duplicate and missing fail-closed checks."""

    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    left_cases = cases[:18]
    right_cases = cases[18:]
    left = tuple((case, spawn_gate._derive_case(case)) for case in left_cases)
    right = tuple((case, spawn_gate._derive_case(case)) for case in right_cases)

    try:
        _merge_declared_groups((left, right + (left[0],)), (left_cases, right_cases))
    except ValueError as exc:
        assert "duplicate logical case" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("intermediate duplicate logical case unexpectedly merged")

    try:
        _merge_declared_groups((left[:-1], right), (left_cases, right_cases))
    except ValueError as exc:
        assert "complete logical case set" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("intermediate incomplete logical case set unexpectedly merged")

    merge_gate.test_partition_merge_rejects_duplicate_logical_case()
    merge_gate.test_partition_merge_rejects_missing_logical_case()


def test_hierarchical_merge_grouping_gate_does_not_expand_truth_claims() -> None:
    # This is bounded local deterministic evidence for two explicit grouping
    # trees over four explicit shard layouts of the established finite 36-case
    # set. It is not evidence for arbitrary associativity, distributed execution,
    # scalability, reliability, performance, production readiness, novelty,
    # patentability, or scientific effect.
    merge_gate.test_partition_merge_gate_does_not_expand_truth_claims()
