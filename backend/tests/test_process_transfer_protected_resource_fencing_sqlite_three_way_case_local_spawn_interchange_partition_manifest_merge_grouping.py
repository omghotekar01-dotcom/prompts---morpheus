from __future__ import annotations

import multiprocessing as mp
from queue import Empty

import pytest

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_manifest as manifest_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_composition as manifested_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_merge_grouping as grouping_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


Case = manifested_gate.Case
Record = manifested_gate.Record


def _layouts(cases: tuple[Case, ...]) -> tuple[tuple[tuple[Case, ...], ...], ...]:
    return (
        (cases,),
        (cases[:18], cases[18:]),
        (cases[::3], cases[1::3], cases[2::3]),
        tuple(cases[index::6] for index in range(6)),
    )


def _spawn_verified_manifested_shards(
    layout: tuple[tuple[Case, ...], ...],
) -> tuple[tuple[Record, ...], ...]:
    payloads = tuple(normalization_gate._normalized_export(shard) for shard in layout)
    manifests = tuple(manifested_gate._export_shard_manifest(payload) for payload in payloads)

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(
            target=manifested_gate._spawn_verify_shard,
            args=(index, payload, manifest, queue),
        )
        for index, (payload, manifest) in enumerate(zip(payloads, manifests, strict=True))
    ]

    try:
        for process in processes:
            process.start()

        indexed_results: list[tuple[int, bytes]] = []
        for _ in processes:
            try:
                indexed_results.append(queue.get(timeout=30))
            except Empty as exc:  # pragma: no cover - diagnostic failure path
                raise AssertionError("spawned manifested interchange shard produced no result") from exc

        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0

        indexed_results.sort(key=lambda item: item[0])
        assert tuple(index for index, _ in indexed_results) == tuple(range(len(payloads)))
        for index, child_manifest in indexed_results:
            assert child_manifest == manifests[index]

        return tuple(
            manifested_gate._verify_shard_manifest(manifest, payload)
            for payload, manifest in zip(payloads, manifests, strict=True)
        )
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        queue.close()
        queue.join_thread()


def test_manifested_shards_preserve_two_explicit_hierarchical_merge_groupings() -> None:
    """Verified manifested shards compose through the two established finite merge trees."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == manifest_gate.EXPECTED_CASE_COUNT == 36

    baseline_payload = normalization_gate._normalized_export(cases)
    baseline_manifest = manifest_gate._export_manifest(baseline_payload)
    expected = manifest_gate._verify_manifest(baseline_manifest, baseline_payload)
    manifested_gate._assert_complete_derivation_invariants(expected)

    for layout in _layouts(cases):
        flattened = tuple(case for shard in layout for case in shard)
        assert len(flattened) == len(set(flattened)) == len(cases)
        assert set(flattened) == set(cases)

        verified_shards = _spawn_verified_manifested_shards(layout)
        assert len(verified_shards) == len(layout)

        for grouped in (
            grouping_gate._left_deep_merge(verified_shards, layout),
            grouping_gate._balanced_merge(verified_shards, layout),
        ):
            assert grouped == expected
            manifested_gate._assert_complete_derivation_invariants(grouped)

            grouped_payload = normalization_gate._normalized_export(
                tuple(case for case, _ in grouped)
            )
            grouped_manifest = manifest_gate._export_manifest(grouped_payload)
            assert grouped_payload == baseline_payload
            assert grouped_manifest == baseline_manifest
            assert manifest_gate._verify_manifest(grouped_manifest, grouped_payload) == expected


def test_manifested_hierarchical_merge_rejects_intermediate_duplicate_and_missing_cases() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    left_cases = cases[:18]
    right_cases = cases[18:]
    verified_left, verified_right = _spawn_verified_manifested_shards((left_cases, right_cases))

    with pytest.raises(ValueError, match="duplicate logical case"):
        grouping_gate._merge_declared_groups(
            (verified_left, verified_right + (verified_left[0],)),
            (left_cases, right_cases),
        )

    with pytest.raises(ValueError, match="complete logical case set"):
        grouping_gate._merge_declared_groups(
            (verified_left[:-1], verified_right),
            (left_cases, right_cases),
        )


def test_manifested_hierarchical_merge_still_rejects_payload_manifest_mismatch() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    left_payload = normalization_gate._normalized_export(left_cases := cases[:18])
    right_payload = normalization_gate._normalized_export(cases[18:])
    left_manifest = manifested_gate._export_shard_manifest(left_payload)

    assert left_cases
    assert left_payload != right_payload
    with pytest.raises(ValueError):
        manifested_gate._verify_shard_manifest(left_manifest, right_payload)


def test_manifested_hierarchical_grouping_gate_does_not_expand_truth_claims() -> None:
    # This is bounded local deterministic composition evidence for two explicit
    # hierarchical merge trees over four explicit manifested shard layouts of
    # the established finite 36-case set. It is not evidence for arbitrary
    # associativity/topology/scheduling, distributed execution or trust,
    # authenticity, durability, scalability, reliability, performance,
    # production readiness, novelty, patentability, or scientific effect.
    manifested_gate.test_manifested_partition_composition_gate_does_not_expand_truth_claims()
