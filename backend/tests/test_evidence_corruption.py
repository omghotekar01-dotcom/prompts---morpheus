from __future__ import annotations

from pathlib import Path

from app.storage import StateStore


def _store(tmp_path: Path) -> StateStore:
    return StateStore(
        db_path=tmp_path / "state.db",
        artifact_root=tmp_path / "artifacts",
    )


def test_payload_tampering_is_detected_at_exact_sequence(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.append_evidence(kind="test", subject="first", payload={"value": 1})
    second = store.append_evidence(kind="test", subject="second", payload={"value": 2})
    assert store.verify_evidence_ledger()["valid"] is True

    with store._lock, store._connection:  # intentional white-box corruption test
        store._connection.execute(
            "UPDATE evidence_ledger SET payload_json = ? WHERE sequence = ?",
            ('{"value":999}', second["sequence"]),
        )

    report = store.verify_evidence_ledger()
    assert report["valid"] is False
    assert report["failed_sequence"] == second["sequence"]
    assert report["evidence_state"] == "EVIDENCE_LEDGER_INTEGRITY_FAILURE"
    assert report["expected_entry_hash"] != report["stored_entry_hash"]
    assert first["entry_hash"] == report["expected_previous_hash"]


def test_previous_hash_tampering_breaks_chain_even_when_payload_is_unchanged(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_evidence(kind="test", subject="one", payload={"ok": True})
    second = store.append_evidence(kind="test", subject="two", payload={"ok": True})

    with store._lock, store._connection:
        store._connection.execute(
            "UPDATE evidence_ledger SET previous_hash = ? WHERE sequence = ?",
            ("f" * 64, second["sequence"]),
        )

    report = store.verify_evidence_ledger()
    assert report["valid"] is False
    assert report["failed_sequence"] == second["sequence"]
    assert report["stored_previous_hash"] == "f" * 64
    assert report["stored_previous_hash"] != report["expected_previous_hash"]


def test_inserted_forged_tail_without_valid_hash_is_detected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    head = store.append_evidence(kind="test", subject="head", payload={"value": 1})

    with store._lock, store._connection:
        store._connection.execute(
            """
            INSERT INTO evidence_ledger(timestamp, kind, subject, payload_json, previous_hash, entry_hash)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-08-29T00:00:00+00:00",
                "forged",
                "tail",
                '{"value":2}',
                head["entry_hash"],
                "0" * 64,
            ),
        )

    report = store.verify_evidence_ledger()
    assert report["valid"] is False
    assert report["evidence_state"] == "EVIDENCE_LEDGER_INTEGRITY_FAILURE"
