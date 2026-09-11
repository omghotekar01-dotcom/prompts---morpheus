from __future__ import annotations

import hashlib

import pytest

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_manifest as manifest_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_composition as manifested_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_group_evidence as group_evidence_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_merge_grouping as manifested_grouping_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_stability as interchange_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


Case = manifested_gate.Case
Record = manifested_gate.Record
LINEAGE_MANIFEST_SCHEMA = "morpheus.case-local-derivation-merge-lineage-manifest-test/v1"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _lineage_manifest_object(
    left_evidence: bytes,
    right_evidence: bytes,
    child_group_manifest: bytes,
    declared_cases: tuple[Case, ...],
) -> dict[str, object]:
    normalized = normalization_gate._normalize_cases(declared_cases)
    return {
        "schema": LINEAGE_MANIFEST_SCHEMA,
        "group_manifest_schema": group_evidence_gate.GROUP_MANIFEST_SCHEMA,
        "ordered_parent_evidence_sha256": [_sha256(left_evidence), _sha256(right_evidence)],
        "child_group_manifest_sha256": _sha256(child_group_manifest),
        "declared_cases_sha256": _sha256(group_evidence_gate._declared_cases_bytes(normalized)),
        "logical_case_count": len(normalized),
        "automatic_control_allowed": False,
    }


def _export_lineage_manifest(
    left_evidence: bytes,
    right_evidence: bytes,
    child_group_manifest: bytes,
    declared_cases: tuple[Case, ...],
) -> bytes:
    return interchange_gate._canonical_json_bytes(
        _lineage_manifest_object(
            left_evidence,
            right_evidence,
            child_group_manifest,
            declared_cases,
        )
    )


def _verify_lineage_manifest(
    manifest: bytes,
    left_evidence: bytes,
    right_evidence: bytes,
    child_group_manifest: bytes,
    declared_cases: tuple[Case, ...],
) -> None:
    if not isinstance(manifest, bytes) or not manifest:
        raise ValueError("merge lineage manifest must be non-empty bytes")
    try:
        raw = interchange_gate.json.loads(manifest.decode("utf-8"))
    except (UnicodeDecodeError, interchange_gate.json.JSONDecodeError) as exc:
        raise ValueError("merge lineage manifest must be canonical UTF-8 JSON") from exc

    expected_keys = {
        "schema",
        "group_manifest_schema",
        "ordered_parent_evidence_sha256",
        "child_group_manifest_sha256",
        "declared_cases_sha256",
        "logical_case_count",
        "automatic_control_allowed",
    }
    if not isinstance(raw, dict) or set(raw) != expected_keys:
        raise ValueError("merge lineage manifest keys do not match schema")
    if raw["schema"] != LINEAGE_MANIFEST_SCHEMA:
        raise ValueError("merge lineage manifest has an incompatible schema")
    if raw["group_manifest_schema"] != group_evidence_gate.GROUP_MANIFEST_SCHEMA:
        raise ValueError("merge lineage manifest references an incompatible group schema")
    if raw["automatic_control_allowed"] is not False:
        raise ValueError("merge lineage manifest cannot authorize automatic control")

    normalized = normalization_gate._normalize_cases(declared_cases)
    expected_parent_digests = [_sha256(left_evidence), _sha256(right_evidence)]
    if raw["ordered_parent_evidence_sha256"] != expected_parent_digests:
        raise ValueError("merge lineage parent evidence digest or order does not match")
    if raw["child_group_manifest_sha256"] != _sha256(child_group_manifest):
        raise ValueError("merge lineage child group evidence digest does not match")
    if raw["logical_case_count"] != len(normalized):
        raise ValueError("merge lineage logical-case count does not match declaration")
    if raw["declared_cases_sha256"] != _sha256(group_evidence_gate._declared_cases_bytes(normalized)):
        raise ValueError("merge lineage declared logical-case digest does not match")
    if interchange_gate._canonical_json_bytes(raw) != manifest:
        raise ValueError("merge lineage manifest is not canonical or does not round-trip exactly")


def _initial_nodes(
    layout: tuple[tuple[Case, ...], ...],
) -> list[tuple[tuple[Record, ...], tuple[Case, ...], bytes]]:
    verified_shards = manifested_grouping_gate._spawn_verified_manifested_shards(layout)
    nodes: list[tuple[tuple[Record, ...], tuple[Case, ...], bytes]] = []
    for records, cases in zip(verified_shards, layout, strict=True):
        payload = normalization_gate._normalized_export(cases)
        evidence = manifested_gate._export_shard_manifest(payload)
        assert manifested_gate._verify_shard_manifest(evidence, payload) == records
        nodes.append((records, cases, evidence))
    return nodes


def _merge_nodes(
    left: tuple[tuple[Record, ...], tuple[Case, ...], bytes],
    right: tuple[tuple[Record, ...], tuple[Case, ...], bytes],
) -> tuple[tuple[tuple[Record, ...], tuple[Case, ...], bytes], bytes]:
    left_records, left_cases, left_evidence = left
    right_records, right_cases, right_evidence = right
    merged, declared, child_manifest = group_evidence_gate._merge_with_group_manifest(
        (left_records, right_records),
        (left_cases, right_cases),
    )
    lineage = _export_lineage_manifest(
        left_evidence,
        right_evidence,
        child_manifest,
        declared,
    )
    _verify_lineage_manifest(
        lineage,
        left_evidence,
        right_evidence,
        child_manifest,
        declared,
    )
    return (merged, declared, child_manifest), lineage


def _left_deep_with_lineage(
    layout: tuple[tuple[Case, ...], ...],
) -> tuple[tuple[Record, ...], tuple[bytes, ...]]:
    nodes = _initial_nodes(layout)
    current = nodes[0]
    lineages: list[bytes] = []
    for node in nodes[1:]:
        current, lineage = _merge_nodes(current, node)
        lineages.append(lineage)
    return current[0], tuple(lineages)


def _balanced_with_lineage(
    layout: tuple[tuple[Case, ...], ...],
) -> tuple[tuple[Record, ...], tuple[bytes, ...]]:
    nodes = _initial_nodes(layout)
    lineages: list[bytes] = []
    while len(nodes) > 1:
        next_nodes: list[tuple[tuple[Record, ...], tuple[Case, ...], bytes]] = []
        for index in range(0, len(nodes), 2):
            if index + 1 == len(nodes):
                next_nodes.append(nodes[index])
                continue
            merged, lineage = _merge_nodes(nodes[index], nodes[index + 1])
            next_nodes.append(merged)
            lineages.append(lineage)
        nodes = next_nodes
    return nodes[0][0], tuple(lineages)


def test_group_evidence_lineage_is_canonical_and_deterministic_for_verified_hierarchies() -> None:
    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == manifest_gate.EXPECTED_CASE_COUNT == 36

    baseline_payload = normalization_gate._normalized_export(cases)
    baseline_manifest = manifest_gate._export_manifest(baseline_payload)
    expected = manifest_gate._verify_manifest(baseline_manifest, baseline_payload)
    manifested_gate._assert_complete_derivation_invariants(expected)

    for layout in manifested_grouping_gate._layouts(cases):
        for build in (_left_deep_with_lineage, _balanced_with_lineage):
            grouped, lineages = build(layout)
            repeated_grouped, repeated_lineages = build(layout)
            assert grouped == repeated_grouped == expected
            assert lineages == repeated_lineages
            assert len(lineages) == max(0, len(layout) - 1)
            manifested_gate._assert_complete_derivation_invariants(grouped)

            final_payload = normalization_gate._normalized_export(tuple(case for case, _ in grouped))
            final_manifest = manifest_gate._export_manifest(final_payload)
            assert final_payload == baseline_payload
            assert final_manifest == baseline_manifest
            assert manifest_gate._verify_manifest(final_manifest, final_payload) == expected


def test_merge_lineage_rejects_parent_substitution_order_change_and_child_change() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    layout = (cases[:12], cases[12:24], cases[24:])
    nodes = _initial_nodes(layout)
    merged, lineage = _merge_nodes(nodes[0], nodes[1])
    _, declared, child_manifest = merged
    left_evidence = nodes[0][2]
    right_evidence = nodes[1][2]

    with pytest.raises(ValueError, match="parent evidence digest or order"):
        _verify_lineage_manifest(
            lineage,
            nodes[2][2],
            right_evidence,
            child_manifest,
            declared,
        )
    with pytest.raises(ValueError, match="parent evidence digest or order"):
        _verify_lineage_manifest(
            lineage,
            right_evidence,
            left_evidence,
            child_manifest,
            declared,
        )

    altered_child = child_manifest + b"\n"
    with pytest.raises(ValueError, match="child group evidence digest"):
        _verify_lineage_manifest(
            lineage,
            left_evidence,
            right_evidence,
            altered_child,
            declared,
        )


def test_merge_lineage_rejects_declared_membership_and_noncanonical_json() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    layout = (cases[:18], cases[18:])
    nodes = _initial_nodes(layout)
    merged, lineage = _merge_nodes(nodes[0], nodes[1])
    _, declared, child_manifest = merged
    left_evidence = nodes[0][2]
    right_evidence = nodes[1][2]

    altered_declared = declared[:-1]
    with pytest.raises(ValueError, match="logical-case count|declared logical-case digest"):
        _verify_lineage_manifest(
            lineage,
            left_evidence,
            right_evidence,
            child_manifest,
            altered_declared,
        )

    raw = interchange_gate.json.loads(lineage.decode("utf-8"))
    noncanonical = interchange_gate.json.dumps(raw, indent=2, sort_keys=False).encode("utf-8")
    with pytest.raises(ValueError, match="canonical"):
        _verify_lineage_manifest(
            noncanonical,
            left_evidence,
            right_evidence,
            child_manifest,
            declared,
        )


def test_merge_lineage_gate_does_not_expand_truth_claims() -> None:
    # The lineage digest binds finite deterministic local test evidence only.
    # It records ordered parent evidence and child group evidence for two explicit
    # merge shapes over four explicit shard layouts of one established 36-case
    # set. It does not establish authenticity, arbitrary topology/scheduling,
    # distributed trust/execution, durability, scalability, reliability rates,
    # performance, production readiness/security, novelty, patentability, or
    # scientific effect.
    assert LINEAGE_MANIFEST_SCHEMA.endswith("/v1")
    group_evidence_gate.test_group_manifest_gate_does_not_expand_truth_claims()
