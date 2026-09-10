from __future__ import annotations

import json
import multiprocessing as mp
from queue import Empty

import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_partition_stability as partition_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_case_local_spawn_stability as spawn_gate
import test_process_transfer_protected_resource_fencing_sqlite_three_way_full_joint_permutation_matrix as full_joint
import test_process_transfer_protected_resource_fencing_sqlite_three_way_joint_permutation_matrix as joint_matrix


Case = spawn_gate.Case
Derived = spawn_gate.Derived
INTERCHANGE_SCHEMA = "morpheus.case-local-derivation-interchange-test/v1"


def _canonical_json_bytes(payload: object) -> bytes:
    """Use the repository's established canonical JSON representation convention."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=True,
    ).encode("utf-8")


def _export_cases(cases: tuple[Case, ...]) -> bytes:
    records = []
    for case in cases:
        sizes, start_order = case
        namespace, literals = spawn_gate._derive_case(case)
        records.append(
            {
                "sizes": list(sizes),
                "start_order": list(start_order),
                "namespace": namespace,
                "literals": list(literals),
            }
        )
    return _canonical_json_bytes(
        {
            "schema": INTERCHANGE_SCHEMA,
            "records": records,
            "automatic_control_allowed": False,
        }
    )


def _import_cases(data: bytes) -> tuple[tuple[Case, Derived], ...]:
    if not isinstance(data, bytes) or not data:
        raise ValueError("derivation interchange payload must be non-empty bytes")
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("derivation interchange payload must be canonical UTF-8 JSON") from exc

    if not isinstance(raw, dict) or set(raw) != {"schema", "records", "automatic_control_allowed"}:
        raise ValueError("derivation interchange envelope keys do not match schema")
    if raw["schema"] != INTERCHANGE_SCHEMA:
        raise ValueError("derivation interchange has an incompatible schema")
    if raw["automatic_control_allowed"] is not False:
        raise ValueError("derivation interchange cannot authorize automatic control")
    if not isinstance(raw["records"], list):
        raise ValueError("derivation interchange records must be a list")

    reconstructed: list[tuple[Case, Derived]] = []
    seen_cases: set[Case] = set()
    for index, record in enumerate(raw["records"]):
        if not isinstance(record, dict) or set(record) != {"sizes", "start_order", "namespace", "literals"}:
            raise ValueError(f"record[{index}] keys do not match schema")
        if not isinstance(record["sizes"], list) or not all(
            isinstance(value, int) and not isinstance(value, bool) for value in record["sizes"]
        ):
            raise ValueError(f"record[{index}].sizes must be an integer list")
        if not isinstance(record["start_order"], list) or not all(
            isinstance(value, str) for value in record["start_order"]
        ):
            raise ValueError(f"record[{index}].start_order must be a string list")
        if not isinstance(record["namespace"], str) or not record["namespace"]:
            raise ValueError(f"record[{index}].namespace must be a non-empty string")
        if not isinstance(record["literals"], list) or not all(
            isinstance(value, str) for value in record["literals"]
        ):
            raise ValueError(f"record[{index}].literals must be a string list")

        case: Case = (tuple(record["sizes"]), tuple(record["start_order"]))
        if case in seen_cases:
            raise ValueError("derivation interchange contains a duplicate logical case")
        seen_cases.add(case)

        supplied: Derived = (record["namespace"], tuple(record["literals"]))
        expected = spawn_gate._derive_case(case)
        if supplied != expected:
            raise ValueError("derivation interchange record does not match deterministic derivation")
        reconstructed.append((case, supplied))

    canonical_cases = tuple(case for case, _ in reconstructed)
    if _export_cases(canonical_cases) != data:
        raise ValueError("derivation interchange payload is not canonical or does not round-trip exactly")
    return tuple(reconstructed)


def _spawn_round_trip(data: bytes, queue: mp.Queue) -> None:
    queue.put(_import_cases(data))


def test_case_local_derivation_is_stable_across_canonical_spawn_interchange() -> None:
    """Round-trip the complete finite derivation set across a strict byte boundary."""

    cases = tuple(full_joint.FULL_JOINT_CASES)
    assert len(cases) == len(set(cases)) == 36

    expected = tuple((case, spawn_gate._derive_case(case)) for case in cases)
    partition_gate._assert_complete_derivation_invariants(dict(expected))

    payload = _export_cases(cases)
    assert payload == _export_cases(cases)
    assert _import_cases(payload) == expected

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [ctx.Process(target=_spawn_round_trip, args=(payload, queue)) for _ in range(2)]

    try:
        for process in processes:
            process.start()

        child_results = []
        for _ in processes:
            try:
                child_results.append(queue.get(timeout=30))
            except Empty as exc:  # pragma: no cover - diagnostic failure path
                raise AssertionError("spawned interchange process produced no result") from exc

        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0

        assert child_results == [expected, expected]
        for child in child_results:
            partition_gate._assert_complete_derivation_invariants(dict(child))
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        queue.close()
        queue.join_thread()


def test_spawn_interchange_gate_rejects_noncanonical_bytes() -> None:
    cases = tuple(full_joint.FULL_JOINT_CASES)
    payload = _export_cases(cases)
    raw = json.loads(payload.decode("utf-8"))
    noncanonical = json.dumps(raw, indent=2, sort_keys=False).encode("utf-8")
    assert noncanonical != payload

    try:
        _import_cases(noncanonical)
    except ValueError as exc:
        assert "canonical" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("noncanonical derivation interchange unexpectedly passed")


def test_spawn_interchange_gate_rejects_tampered_derivation() -> None:
    cases = tuple(full_joint.FULL_JOINT_CASES)
    raw = json.loads(_export_cases(cases).decode("utf-8"))
    raw["records"][0]["namespace"] += "-tampered"
    tampered = _canonical_json_bytes(raw)

    try:
        _import_cases(tampered)
    except ValueError as exc:
        assert "does not match deterministic derivation" in str(exc)
    else:  # pragma: no cover - must fail closed
        raise AssertionError("tampered derivation interchange unexpectedly passed")


def test_spawn_interchange_gate_does_not_expand_truth_claims() -> None:
    # This verifies strict canonical JSON byte round-trip and deterministic
    # derivation equality across two fresh local spawned interpreters for the
    # established finite 36 logical cases. It is not arbitrary serialization
    # portability, durability, distributed execution, statistical/reliability,
    # performance, production-readiness, novelty, or scientific-effect evidence.
    joint_matrix.test_three_way_joint_permutation_gate_does_not_expand_truth_claims()
