from __future__ import annotations

from pathlib import Path

from app.engine import synthesize
from app.models import CalibrationMeasurement, CalibrationProfile
from app.parser import parse_workload_text
from app.storage import StateStore


SPEC = """
version: mws-0.1
name: storage_test
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
queries:
  - kind: point_lookup
    field: id
    weight: 1.0
constraints:
  memory_mb: 16
""".strip()


def test_state_store_persists_run_metadata_and_content_addressed_artifact(tmp_path: Path) -> None:
    store = StateStore(db_path=tmp_path / "state.db", artifact_root=tmp_path / "artifacts")
    spec = parse_workload_text(SPEC)
    result = synthesize(spec)

    run_id = store.save_synthesis(spec, SPEC, result)
    runs = store.list_runs()
    assert runs and runs[0]["run_id"] == run_id
    assert runs[0]["spec_hash"] == result.spec_hash

    detail = store.get_run(run_id)
    assert detail is not None
    assert detail["name"] == "storage_test"
    assert detail["result"]["winner"] is not None

    metadata = store.store_artifact(
        content="#pragma once\n// deterministic test artifact\n",
        kind="generated_cpp20_header",
        file_name="generated.hpp",
        evidence_state="GENERATED_NOT_EXTERNALLY_VERIFIED",
        candidate_id=result.winner.id if result.winner else None,
        spec_hash=result.spec_hash,
    )
    assert len(metadata["sha256"]) == 64
    assert metadata["size_bytes"] > 0

    loaded = store.read_artifact(metadata["sha256"])
    assert loaded is not None
    loaded_metadata, content = loaded
    assert loaded_metadata["sha256"] == metadata["sha256"]
    assert "deterministic test artifact" in content
    assert store.read_artifact("../escape") is None

    summary = store.summary()
    assert summary["workloads"] == 1
    assert summary["synthesis_runs"] == 1
    assert summary["artifacts"] == 1


def test_calibration_profiles_survive_store_reopen_and_preserve_explicit_activation(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    artifacts = tmp_path / "artifacts"
    profile = CalibrationProfile(
        id="machine-a",
        protocol="morpheus-calibration-v2",
        record_count=1000,
        operations=5000,
        machine={"cpu": "test"},
        measurements=[
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                operation="point_lookup",
                ns_per_op=42.0,
            )
        ],
    )

    first = StateStore(db_path=db, artifact_root=artifacts)
    first.save_calibration_profile(profile, activate=True)
    profiles, active = first.load_calibration_profiles()
    assert [item.id for item in profiles] == ["machine-a"]
    assert active == "machine-a"

    reopened = StateStore(db_path=db, artifact_root=artifacts)
    profiles, active = reopened.load_calibration_profiles()
    assert profiles[0].measurements[0].ns_per_op == 42.0
    assert active == "machine-a"
    reopened.set_active_calibration(None)
    _, active = reopened.load_calibration_profiles()
    assert active is None


def test_evidence_ledger_detects_tampering(tmp_path: Path) -> None:
    store = StateStore(db_path=tmp_path / "state.db", artifact_root=tmp_path / "artifacts")
    first = store.append_evidence(kind="test", subject="alpha", payload={"value": 1})
    second = store.append_evidence(kind="test", subject="beta", payload={"value": 2})
    assert first["previous_hash"] == "0" * 64
    assert second["previous_hash"] == first["entry_hash"]

    verified = store.verify_evidence_ledger()
    assert verified["valid"] is True
    assert verified["entries"] == 2
    assert verified["head_hash"] == second["entry_hash"]

    # Deliberately corrupt the first persisted payload to prove verification is
    # checking the chain, not merely reporting a stored status flag.
    with store._lock, store._connection:  # noqa: SLF001 - integrity fault injection for the test only
        store._connection.execute(  # noqa: SLF001
            "UPDATE evidence_ledger SET payload_json = ? WHERE sequence = 1",
            ('{"value":999}',),
        )
    failed = store.verify_evidence_ledger()
    assert failed["valid"] is False
    assert failed["failed_sequence"] == 1
