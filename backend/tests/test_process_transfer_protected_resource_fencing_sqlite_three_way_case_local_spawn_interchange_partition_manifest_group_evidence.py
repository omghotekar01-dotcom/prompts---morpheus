from __future__ import annotations

import hashlib

import pytest

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_manifest as manifest_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_composition as manifested_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_merge_grouping as manifested_grouping_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_merge_grouping as grouping_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_stability as interchange_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


Case = manifested_gate.Case
Record = manifested_gate.Record
GROUP_MANIFEST_SCHEMA = "morpheus.case-local-derivation-group-evidence-manifest-test/v1"


def _declared_cases_bytes(cases: tuple[Case, ...]) -> bytes:
    normalized = normalization_gate._normalize_cases(cases)
    return interchange_gate._canonical_json_bytes(
        [
            {"sizes": list(sizes), "start_order": list(start_order)}
            for sizes, start_order in normalized
        ]
    )


def _group_manifest_object(declared_cases: tuple[Case, ...], payload: bytes) -> dict[str, object]:
    normalized = normalization_gate._normalize_cases(declared_cases)
    reconstructed = interchange_gate._import_cases(payload)
    if tuple(case for case, _ in reconstructed) != normalized:
        raise ValueError("group evidence manifest payload does not match declared logical-case set")
    return {
        "schema": GROUP_MANIFEST_SCHEMA,
        "interchange_schema": interchange_gate.INTERCHANGE_SCHEMA,
        "logical_case_count": len(normalized),
        "declared_cases_sha256": hashlib.sha256(_declared_cases_bytes(normalized)).hexdigest(),
        "canonical_payload_bytes": len(payload),
        "canonical_payload_sha256": hashlib.sha256(payload).hexdigest(),
        "automatic_control_allowed": False,
    }


def _export_group_manifest(declared_cases: tuple[Case, ...], payload: bytes) -> bytes:
    return interchange_gate._canonical_json_bytes(_group_manifest_object(declared_cases, payload))


def _verify_group_manifest(
    manifest: bytes,
    declared_cases: tuple[Case, ...],
    payload: bytes,
) -> tuple[Record, ...]:
    if not isinstance(manifest, bytes) or not manifest:
        raise ValueError("group evidence manifest must be non-empty bytes")
    try:
        raw = interchange_gate.json.loads(manifest.decode("utf-8"))
    except (UnicodeDecodeError, interchange_gate.json.JSONDecodeError) as exc:
        raise ValueError("group evidence manifest must be canonical UTF-8 JSON") from exc

    expected_keys = {
        "schema",
        "interchange_schema",
        "logical_case_count",
        "declared_cases_sha256",
        "canonical_payload_bytes",
        "canonical_payload_sha256",
        "automatic_control_allowed",
    }
    if not isinstance(raw, dict) or set(raw) != expected_keys:
        raise ValueError("group evidence manifest keys do not match schema")
    if raw["schema"] != GROUP_MANIFEST_SCHEMA:
        raise ValueError("group evidence manifest has an incompatible schema")
    if raw["interchange_schema"] != interchange_gate.INTERCHANGE_SCHEMA:
        raise ValueError("group evidence manifest references an incompatible interchange schema")
    if raw["automatic_control_allowed"] is not False:
        raise ValueError("group evidence manifest cannot authorize automatic control")

    normalized = normalization_gate._normalize_cases(declared_cases)
    if raw["logical_case_count"] != len(normalized):
        raise ValueError("group evidence manifest logical-case cardinality does not match declaration")
    declared_digest = hashlib.sha256(_declared_cases_bytes(normalized)).hexdigest()
    if raw["declared_cases_sha256"] != declared_digest:
        raise ValueError("group evidence manifest declared logical-case digest does not match")
    if raw["canonical_payload_bytes"] != len(payload):
        raise ValueError("group evidence manifest payload byte length does not match")
    if raw["canonical_payload_sha256"] != hashlib.sha256(payload).hexdigest():
        raise ValueError("group evidence manifest payload digest does not match")
    if interchange_gate._canonical_json_bytes(raw) != manifest:
        raise ValueError("group evidence manifest is not canonical or does not round-trip exactly")

    reconstructed = interchange_gate._import_cases(payload)
    if tuple(case for case, _ in reconstructed) != normalized:
        raise ValueError("group evidence manifest payload does not match declared logical-case set")
    return reconstructed


def _merge_with_group_manifest(
    record_groups: tuple[tuple[Record, ...], ...],
    case_groups: tuple[tuple[Case, ...], ...],
) -> tuple[tuple[Record, ...], tuple[Case, ...], bytes]:
    declared = tuple(case for group in case_groups for case in group)
    merged = grouping_gate._merge_declared_groups(record_groups, case_groups)
    payload = normalization_gate._normalized_export(tuple(case for case, _ in merged))
    manifest = _export_group_manifest(declared, payload)
    assert _verify_group_manifest(manifest, declared, payload) == merged
    return merged, declared, manifest


def _left_deep_manifested_merge(
    shards: tuple[tuple[Record, ...], ...],
    layout: tuple[tuple[Case, ...], ...],
) -> tuple[Record, ...]:
    merged = shards[0]
    declared = layout[0]
    for shard, cases in zip(shards[1:], layout[1:]):
        merged, declared, _ = _merge_with_group_manifest((merged, shard), (declared, cases))
    return merged


def _balanced_manifested_merge(
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
            merged, declared, _ = _merge_with_group_manifest(
                (record_groups[index], record_groups[index + 1]),
                (case_groups[index], case_groups[index + 1]),
            )
            next_records.append(merged)
            next_cases.append(declared)
        record_groups = next_records
        case_groups = next_cases
    return record_groups[0]


def test_intermediate_group_manifests_preserve_both_verified_hierarchies() -> None:
    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == manifest_gate.EXPECTED_CASE_COUNT == 36

    baseline_payload = normalization_gate._normalized_export(cases)
    baseline_manifest = manifest_gate._export_manifest(baseline_payload)
    expected = manifest_gate._verify_manifest(baseline_manifest, baseline_payload)
    manifested_gate._assert_complete_derivation_invariants(expected)

    for layout in manifested_grouping_gate._layouts(cases):
        verified_shards = manifested_grouping_gate._spawn_verified_manifested_shards(layout)
        for grouped in (
            _left_deep_manifested_merge(verified_shards, layout),
            _balanced_manifested_merge(verified_shards, layout),
        ):
            assert grouped == expected
            manifested_gate._assert_complete_derivation_invariants(grouped)
            final_payload = normalization_gate._normalized_export(tuple(case for case, _ in grouped))
            final_manifest = manifest_gate._export_manifest(final_payload)
            assert final_payload == baseline_payload
            assert final_manifest == baseline_manifest


def test_group_manifest_rejects_altered_payload_and_declared_membership() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    declared = cases[:18]
    payload = normalization_gate._normalized_export(declared)
    manifest = _export_group_manifest(declared, payload)

    with pytest.raises(ValueError, match="byte length|digest"):
        _verify_group_manifest(manifest, declared, payload + b"\n")

    altered_declared = declared[:-1] + (cases[18],)
    with pytest.raises(ValueError, match="declared logical-case digest|payload does not match"):
        _verify_group_manifest(manifest, altered_declared, payload)


def test_group_manifest_rejects_duplicate_missing_and_noncanonical_boundaries() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    left_cases, right_cases = cases[:18], cases[18:]
    verified_left, verified_right = manifested_grouping_gate._spawn_verified_manifested_shards(
        (left_cases, right_cases)
    )

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

    payload = normalization_gate._normalized_export(left_cases)
    raw = interchange_gate.json.loads(_export_group_manifest(left_cases, payload).decode("utf-8"))
    noncanonical = interchange_gate.json.dumps(raw, indent=2, sort_keys=False).encode("utf-8")
    with pytest.raises(ValueError, match="canonical"):
        _verify_group_manifest(noncanonical, left_cases, payload)


def test_group_manifest_gate_does_not_expand_truth_claims() -> None:
    # SHA-256 binds only deterministic local test evidence for explicitly declared
    # intermediate logical-case sets and canonical payload bytes. This finite gate
    # covers two explicit hierarchy shapes over four explicit shard layouts of the
    # established 36-case set. It does not establish authenticity, arbitrary
    # topology/scheduling, distributed trust/execution, durability, scalability,
    # reliability rates, performance, production readiness/security, novelty,
    # patentability, or scientific effect.
    manifested_grouping_gate.test_manifested_hierarchical_grouping_gate_does_not_expand_truth_claims()
