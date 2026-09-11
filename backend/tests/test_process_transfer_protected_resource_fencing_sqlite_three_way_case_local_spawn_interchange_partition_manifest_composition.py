from __future__ import annotations

import hashlib
import multiprocessing as mp
from queue import Empty

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_manifest as manifest_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_merge as merge_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_stability as partition_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_stability as interchange_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_stability as spawn_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


SHARD_MANIFEST_SCHEMA = "morpheus.case-local-derivation-shard-evidence-manifest-test/v1"
Case = spawn_gate.Case
Derived = spawn_gate.Derived
Record = tuple[Case, Derived]


def _shard_manifest_object(payload: bytes) -> dict[str, object]:
    records = interchange_gate._import_cases(payload)
    if not records:
        raise ValueError("shard evidence manifest requires at least one logical case")
    return {
        "schema": SHARD_MANIFEST_SCHEMA,
        "interchange_schema": interchange_gate.INTERCHANGE_SCHEMA,
        "logical_case_count": len(records),
        "canonical_payload_bytes": len(payload),
        "canonical_payload_sha256": hashlib.sha256(payload).hexdigest(),
        "automatic_control_allowed": False,
    }


def _export_shard_manifest(payload: bytes) -> bytes:
    return interchange_gate._canonical_json_bytes(_shard_manifest_object(payload))


def _verify_shard_manifest(manifest: bytes, payload: bytes) -> tuple[Record, ...]:
    if not isinstance(manifest, bytes) or not manifest:
        raise ValueError("shard evidence manifest must be non-empty bytes")

    try:
        raw = interchange_gate.json.loads(manifest.decode("utf-8"))
    except (UnicodeDecodeError, interchange_gate.json.JSONDecodeError) as exc:
        raise ValueError("shard evidence manifest must be canonical UTF-8 JSON") from exc

    expected_keys = {
        "schema",
        "interchange_schema",
        "logical_case_count",
        "canonical_payload_bytes",
        "canonical_payload_sha256",
        "automatic_control_allowed",
    }
    if not isinstance(raw, dict) or set(raw) != expected_keys:
        raise ValueError("shard evidence manifest keys do not match schema")
    if raw["schema"] != SHARD_MANIFEST_SCHEMA:
        raise ValueError("shard evidence manifest has an incompatible schema")
    if raw["interchange_schema"] != interchange_gate.INTERCHANGE_SCHEMA:
        raise ValueError("shard evidence manifest references an incompatible interchange schema")
    if raw["automatic_control_allowed"] is not False:
        raise ValueError("shard evidence manifest cannot authorize automatic control")
    if not isinstance(raw["logical_case_count"], int) or isinstance(raw["logical_case_count"], bool) or raw["logical_case_count"] <= 0:
        raise ValueError("shard evidence manifest logical-case count must be a positive integer")
    if raw["canonical_payload_bytes"] != len(payload):
        raise ValueError("shard evidence manifest payload byte length does not match")
    if raw["canonical_payload_sha256"] != hashlib.sha256(payload).hexdigest():
        raise ValueError("shard evidence manifest payload digest does not match")
    if interchange_gate._canonical_json_bytes(raw) != manifest:
        raise ValueError("shard evidence manifest is not canonical or does not round-trip exactly")

    records = interchange_gate._import_cases(payload)
    if len(records) != raw["logical_case_count"]:
        raise ValueError("shard evidence manifest logical-case count does not match payload")
    return records


def _spawn_verify_shard(
    shard_index: int,
    payload: bytes,
    manifest: bytes,
    queue: mp.Queue,
) -> None:
    _verify_shard_manifest(manifest, payload)
    queue.put((shard_index, _export_shard_manifest(payload)))


def _round_trip_manifested_layout(layout: tuple[tuple[Case, ...], ...]) -> tuple[Record, ...]:
    payloads = tuple(normalization_gate._normalized_export(shard) for shard in layout)
    manifests = tuple(_export_shard_manifest(payload) for payload in payloads)

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(
            target=_spawn_verify_shard,
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

        verified_shards = tuple(
            _verify_shard_manifest(manifest, payload)
            for payload, manifest in zip(payloads, manifests, strict=True)
        )
        return merge_gate._merge_complete_shards(
            verified_shards,
            tuple(full_joint.FULL_JOINT_CASES),
        )
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        queue.close()
        queue.join_thread()


def test_manifested_shards_merge_to_single_shot_payload_and_manifest() -> None:
    """Four explicit manifested shard layouts compose to the same finite final evidence."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == manifest_gate.EXPECTED_CASE_COUNT == 36

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

    baseline_payload = normalization_gate._normalized_export(cases)
    baseline_manifest = manifest_gate._export_manifest(baseline_payload)
    expected = manifest_gate._verify_manifest(baseline_manifest, baseline_payload)
    partition_gate._assert_complete_derivation_invariants(dict(expected))

    for layout in layouts:
        merged = _round_trip_manifested_layout(layout)
        assert merged == expected
        partition_gate._assert_complete_derivation_invariants(dict(merged))

        merged_payload = normalization_gate._normalized_export(tuple(case for case, _ in merged))
        merged_manifest = manifest_gate._export_manifest(merged_payload)
        assert merged_payload == baseline_payload
        assert merged_manifest == baseline_manifest
        assert manifest_gate._verify_manifest(merged_manifest, merged_payload) == expected


def test_individually_valid_manifested_shards_still_reject_duplicate_on_merge() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    duplicate_layout = (cases[:18], cases[18:] + (cases[0],))

    verified_shards = []
    for shard in duplicate_layout:
        payload = normalization_gate._normalized_export(shard)
        manifest = _export_shard_manifest(payload)
        verified_shards.append(_verify_shard_manifest(manifest, payload))

    try:
        merge_gate._merge_complete_shards(tuple(verified_shards), cases)
    except ValueError as exc:
        assert "duplicate logical case" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("duplicate logical case across valid manifested shards unexpectedly merged")


def test_individually_valid_manifested_shards_still_reject_missing_case_on_merge() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    incomplete_layout = (cases[:18], cases[18:-1])

    verified_shards = []
    for shard in incomplete_layout:
        payload = normalization_gate._normalized_export(shard)
        manifest = _export_shard_manifest(payload)
        verified_shards.append(_verify_shard_manifest(manifest, payload))

    try:
        merge_gate._merge_complete_shards(tuple(verified_shards), cases)
    except ValueError as exc:
        assert "complete logical case set" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("incomplete logical case set across valid manifested shards unexpectedly merged")


def test_shard_manifest_rejects_payload_or_manifest_mismatch() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))[:12]
    payload = normalization_gate._normalized_export(cases)
    manifest = _export_shard_manifest(payload)

    altered_payload = payload + b"\n"
    try:
        _verify_shard_manifest(manifest, altered_payload)
    except ValueError as exc:
        assert "byte length" in str(exc) or "digest" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("altered shard payload unexpectedly matched its evidence manifest")

    raw = interchange_gate.json.loads(manifest.decode("utf-8"))
    raw["canonical_payload_sha256"] = "0" * 64
    altered_manifest = interchange_gate._canonical_json_bytes(raw)
    try:
        _verify_shard_manifest(altered_manifest, payload)
    except ValueError as exc:
        assert "digest" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("altered shard evidence manifest unexpectedly passed")


def test_manifested_partition_composition_gate_does_not_expand_truth_claims() -> None:
    # This is bounded local deterministic composition evidence for per-shard
    # integrity metadata and four explicit shard layouts over the established
    # finite 36-case set. It is not evidence for authenticity, adversarial trust,
    # arbitrary sharding/scheduling, distributed execution, durability, scalability,
    # reliability, performance, production readiness, novelty, or scientific effect.
    manifest_gate.test_evidence_manifest_gate_does_not_expand_truth_claims()
