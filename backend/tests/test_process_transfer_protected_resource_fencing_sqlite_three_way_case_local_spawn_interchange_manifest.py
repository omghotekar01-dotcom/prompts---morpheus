from __future__ import annotations

import hashlib
import multiprocessing as mp
from queue import Empty

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_normalization as normalization_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_interchange_stability as interchange_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_partition_stability as partition_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_stability as spawn_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint


MANIFEST_SCHEMA = "morpheus.case-local-derivation-evidence-manifest-test/v1"
EXPECTED_CASE_COUNT = 36


def _manifest_object(payload: bytes) -> dict[str, object]:
    reconstructed = interchange_gate._import_cases(payload)
    if len(reconstructed) != EXPECTED_CASE_COUNT:
        raise ValueError("evidence manifest requires the established 36-case logical set")
    return {
        "schema": MANIFEST_SCHEMA,
        "interchange_schema": interchange_gate.INTERCHANGE_SCHEMA,
        "logical_case_count": len(reconstructed),
        "canonical_payload_bytes": len(payload),
        "canonical_payload_sha256": hashlib.sha256(payload).hexdigest(),
        "automatic_control_allowed": False,
    }


def _export_manifest(payload: bytes) -> bytes:
    return interchange_gate._canonical_json_bytes(_manifest_object(payload))


def _verify_manifest(manifest: bytes, payload: bytes) -> tuple[tuple[spawn_gate.Case, spawn_gate.Derived], ...]:
    if not isinstance(manifest, bytes) or not manifest:
        raise ValueError("evidence manifest must be non-empty bytes")

    try:
        raw = interchange_gate.json.loads(manifest.decode("utf-8"))
    except (UnicodeDecodeError, interchange_gate.json.JSONDecodeError) as exc:
        raise ValueError("evidence manifest must be canonical UTF-8 JSON") from exc

    expected_keys = {
        "schema",
        "interchange_schema",
        "logical_case_count",
        "canonical_payload_bytes",
        "canonical_payload_sha256",
        "automatic_control_allowed",
    }
    if not isinstance(raw, dict) or set(raw) != expected_keys:
        raise ValueError("evidence manifest keys do not match schema")
    if raw["schema"] != MANIFEST_SCHEMA:
        raise ValueError("evidence manifest has an incompatible schema")
    if raw["interchange_schema"] != interchange_gate.INTERCHANGE_SCHEMA:
        raise ValueError("evidence manifest references an incompatible interchange schema")
    if raw["automatic_control_allowed"] is not False:
        raise ValueError("evidence manifest cannot authorize automatic control")
    if raw["logical_case_count"] != EXPECTED_CASE_COUNT:
        raise ValueError("evidence manifest logical-case cardinality does not match the established set")
    if raw["canonical_payload_bytes"] != len(payload):
        raise ValueError("evidence manifest payload byte length does not match")
    if raw["canonical_payload_sha256"] != hashlib.sha256(payload).hexdigest():
        raise ValueError("evidence manifest payload digest does not match")
    if interchange_gate._canonical_json_bytes(raw) != manifest:
        raise ValueError("evidence manifest is not canonical or does not round-trip exactly")

    reconstructed = interchange_gate._import_cases(payload)
    if len(reconstructed) != raw["logical_case_count"]:
        raise ValueError("evidence manifest logical-case cardinality does not match payload")
    return reconstructed


def _spawn_manifest_round_trip(payload: bytes, queue: mp.Queue) -> None:
    manifest = _export_manifest(payload)
    queue.put((manifest, _verify_manifest(manifest, payload)))


def test_canonical_interchange_has_reproducible_evidence_manifest_across_spawn() -> None:
    """The finite canonical 36-case payload has one deterministic local evidence manifest."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == EXPECTED_CASE_COUNT

    payload = normalization_gate._normalized_export(cases)
    expected = interchange_gate._import_cases(payload)
    partition_gate._assert_complete_derivation_invariants(dict(expected))

    manifest = _export_manifest(payload)
    assert manifest == _export_manifest(payload)
    assert _verify_manifest(manifest, payload) == expected

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [ctx.Process(target=_spawn_manifest_round_trip, args=(payload, queue)) for _ in range(2)]

    try:
        for process in processes:
            process.start()

        child_results = []
        for _ in processes:
            try:
                child_results.append(queue.get(timeout=30))
            except Empty as exc:  # pragma: no cover - diagnostic failure path
                raise AssertionError("spawned evidence-manifest process produced no result") from exc

        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0

        assert child_results == [(manifest, expected), (manifest, expected)]
        for child_manifest, child_records in child_results:
            assert child_manifest == manifest
            partition_gate._assert_complete_derivation_invariants(dict(child_records))
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        queue.close()
        queue.join_thread()


def test_evidence_manifest_rejects_altered_payload_bytes() -> None:
    cases = tuple(full_joint.FULL_JOINT_CASES)
    payload = normalization_gate._normalized_export(cases)
    manifest = _export_manifest(payload)
    altered_payload = payload + b"\n"
    assert altered_payload != payload

    try:
        _verify_manifest(manifest, altered_payload)
    except ValueError as exc:
        assert "byte length" in str(exc) or "digest" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("altered payload bytes unexpectedly matched evidence manifest")


def test_evidence_manifest_rejects_altered_manifest_fields() -> None:
    cases = tuple(full_joint.FULL_JOINT_CASES)
    payload = normalization_gate._normalized_export(cases)
    manifest = _export_manifest(payload)
    raw = interchange_gate.json.loads(manifest.decode("utf-8"))

    mutations = (
        ("schema", MANIFEST_SCHEMA + "-other", "incompatible schema"),
        ("interchange_schema", interchange_gate.INTERCHANGE_SCHEMA + "-other", "interchange schema"),
        ("logical_case_count", EXPECTED_CASE_COUNT - 1, "cardinality"),
        ("canonical_payload_bytes", len(payload) + 1, "byte length"),
        ("canonical_payload_sha256", "0" * 64, "digest"),
        ("automatic_control_allowed", True, "automatic control"),
    )

    for field, value, message in mutations:
        altered = dict(raw)
        altered[field] = value
        altered_bytes = interchange_gate._canonical_json_bytes(altered)
        try:
            _verify_manifest(altered_bytes, payload)
        except ValueError as exc:
            assert message in str(exc)
        else:  # pragma: no cover - must fail closed
            raise AssertionError(f"altered evidence-manifest field {field!r} unexpectedly passed")


def test_evidence_manifest_rejects_noncanonical_bytes() -> None:
    cases = tuple(full_joint.FULL_JOINT_CASES)
    payload = normalization_gate._normalized_export(cases)
    raw = interchange_gate.json.loads(_export_manifest(payload).decode("utf-8"))
    noncanonical = interchange_gate.json.dumps(raw, indent=2, sort_keys=False).encode("utf-8")

    try:
        _verify_manifest(noncanonical, payload)
    except ValueError as exc:
        assert "canonical" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("noncanonical evidence manifest unexpectedly passed")


def test_evidence_manifest_gate_does_not_expand_truth_claims() -> None:
    # SHA-256 is used here only to bind this finite canonical local test payload to
    # deterministic reproducibility metadata. This does not establish authenticity,
    # adversarial tamper resistance, durability, distributed execution, scalability,
    # reliability, performance, production security/readiness, novelty, patentability,
    # or scientific effect.
    interchange_gate.test_spawn_interchange_gate_does_not_expand_truth_claims()
