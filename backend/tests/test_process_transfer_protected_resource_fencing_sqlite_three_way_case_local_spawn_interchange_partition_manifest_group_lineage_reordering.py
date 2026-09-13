from __future__ import annotations

import pytest

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_manifest as manifest_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_composition as manifested_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_group_lineage as lineage_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_partition_manifest_reordering as reordering_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


def _reordered_layouts(cases):
    for layout in reordering_gate._layouts(cases):
        yield reordering_gate._reverse_shards_and_records(layout)
        yield reordering_gate._rotate_shards_with_alternating_record_reversal(layout)


def test_reordered_manifested_shards_preserve_deterministic_lineage_per_exact_layout() -> None:
    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == manifest_gate.EXPECTED_CASE_COUNT == 36

    baseline_payload = normalization_gate._normalized_export(cases)
    baseline_manifest = manifest_gate._export_manifest(baseline_payload)
    expected = manifest_gate._verify_manifest(baseline_manifest, baseline_payload)
    manifested_gate._assert_complete_derivation_invariants(expected)

    for reordered in _reordered_layouts(cases):
        flattened = tuple(case for shard in reordered for case in shard)
        assert len(flattened) == len(set(flattened)) == len(cases)
        assert set(flattened) == set(cases)

        for build in (lineage_gate._left_deep_with_lineage, lineage_gate._balanced_with_lineage):
            grouped, lineages = build(reordered)
            repeated_grouped, repeated_lineages = build(reordered)

            assert grouped == repeated_grouped == expected
            assert lineages == repeated_lineages
            assert len(lineages) == max(0, len(reordered) - 1)
            manifested_gate._assert_complete_derivation_invariants(grouped)

            final_payload = normalization_gate._normalized_export(tuple(case for case, _ in grouped))
            final_manifest = manifest_gate._export_manifest(final_payload)
            assert final_payload == baseline_payload
            assert final_manifest == baseline_manifest
            assert manifest_gate._verify_manifest(final_manifest, final_payload) == expected


def test_reordered_lineage_keeps_parent_order_and_substitution_fail_closed() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    base_layout = (cases[:12], cases[12:24], cases[24:])
    reordered = reordering_gate._reverse_shards_and_records(base_layout)
    nodes = lineage_gate._initial_nodes(reordered)

    merged, lineage = lineage_gate._merge_nodes(nodes[0], nodes[1])
    _, declared, child_manifest = merged
    left_evidence = nodes[0][2]
    right_evidence = nodes[1][2]

    with pytest.raises(ValueError, match="parent evidence digest or order"):
        lineage_gate._verify_lineage_manifest(
            lineage,
            right_evidence,
            left_evidence,
            child_manifest,
            declared,
        )

    with pytest.raises(ValueError, match="parent evidence digest or order"):
        lineage_gate._verify_lineage_manifest(
            lineage,
            nodes[2][2],
            right_evidence,
            child_manifest,
            declared,
        )


def test_reordered_lineage_keeps_child_membership_and_canonical_json_fail_closed() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    base_layout = (cases[:18], cases[18:])
    reordered = reordering_gate._rotate_shards_with_alternating_record_reversal(base_layout)
    nodes = lineage_gate._initial_nodes(reordered)

    merged, lineage = lineage_gate._merge_nodes(nodes[0], nodes[1])
    _, declared, child_manifest = merged
    left_evidence = nodes[0][2]
    right_evidence = nodes[1][2]

    with pytest.raises(ValueError, match="child group evidence digest"):
        lineage_gate._verify_lineage_manifest(
            lineage,
            left_evidence,
            right_evidence,
            child_manifest + b"\n",
            declared,
        )

    with pytest.raises(ValueError, match="logical-case count|declared logical-case digest"):
        lineage_gate._verify_lineage_manifest(
            lineage,
            left_evidence,
            right_evidence,
            child_manifest,
            declared[:-1],
        )

    raw = lineage_gate.interchange_gate.json.loads(lineage.decode("utf-8"))
    noncanonical = lineage_gate.interchange_gate.json.dumps(raw, indent=2, sort_keys=False).encode("utf-8")
    with pytest.raises(ValueError, match="canonical"):
        lineage_gate._verify_lineage_manifest(
            noncanonical,
            left_evidence,
            right_evidence,
            child_manifest,
            declared,
        )


def test_reordered_lineage_keeps_shard_manifest_mismatch_fail_closed() -> None:
    cases = normalization_gate._normalize_cases(tuple(full_joint.FULL_JOINT_CASES))
    base_layout = (cases[:18], cases[18:])
    reordered = reordering_gate._reverse_shards_and_records(base_layout)

    left_payload = normalization_gate._normalized_export(reordered[0])
    right_payload = normalization_gate._normalized_export(reordered[1])
    left_manifest = manifested_gate._export_shard_manifest(left_payload)

    assert left_payload != right_payload
    with pytest.raises(ValueError):
        manifested_gate._verify_shard_manifest(left_manifest, right_payload)


def test_reordered_lineage_gate_does_not_expand_truth_claims() -> None:
    # Finite deterministic local provenance evidence only. Repeating an exact
    # reordered layout/topology must reproduce its lineage bytes, but lineage
    # bytes are allowed to differ when the declared ordered parent evidence
    # differs. This does not establish arbitrary ordering/topology/scheduling,
    # authenticity, distributed trust/execution, durability, scalability,
    # reliability rates, performance, production readiness/security, novelty,
    # patentability, or scientific effect.
    assert lineage_gate.LINEAGE_MANIFEST_SCHEMA.endswith("/v1")
    lineage_gate.test_merge_lineage_gate_does_not_expand_truth_claims()
