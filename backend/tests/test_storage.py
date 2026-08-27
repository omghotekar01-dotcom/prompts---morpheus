from __future__ import annotations

from pathlib import Path

from app.engine import synthesize
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
