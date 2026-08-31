from __future__ import annotations

from pathlib import Path

from app.idempotency import IdempotencyJournal
from app.pilot_readiness import build_pilot_readiness
from app.storage import StateStore
from app.toolchain import Toolchain


def _toolchain() -> Toolchain:
    return Toolchain(kind="gnu", executable="/opt/test/g++", version="g++ test 1")


def _store(tmp_path: Path) -> StateStore:
    return StateStore(db_path=tmp_path / "state.db", artifact_root=tmp_path / "artifacts")


def _journal(tmp_path: Path) -> IdempotencyJournal:
    return IdempotencyJournal(tmp_path / "idempotency.db")


def test_guarded_single_node_pilot_can_be_ready_without_active_calibration(tmp_path: Path) -> None:
    store = _store(tmp_path)
    report = build_pilot_readiness(
        store=store,
        journal=_journal(tmp_path),
        environment={
            "MORPHEUS_API_KEY": "pilot-secret-with-more-than-24-chars",
            "MORPHEUS_RATE_LIMIT_PER_MINUTE": "120",
        },
        toolchain_fn=_toolchain,
    )

    assert report["ready"] is True
    assert report["state"] == "PILOT_READY_SINGLE_NODE_SCOPE"
    assert report["blockers"] == []
    assert report["advisories"] == ["active_calibration_profile"]
    assert len(report["readiness_sha256"]) == 64
    assert report["scope"]["deployment_shape"] == "SINGLE_NODE_LOCAL_CONTROL_PLANE"
    assert report["scope"]["durable_idempotency"] == "SQLITE_SINGLE_NODE"
    assert any("not a security certification" in item for item in report["truth_boundaries"])


def test_unprotected_ephemeral_process_fails_pilot_readiness(tmp_path: Path) -> None:
    store = StateStore(db_path=":memory:", artifact_root=tmp_path / "artifacts")
    report = build_pilot_readiness(
        store=store,
        journal=IdempotencyJournal(":memory:"),
        environment={"MORPHEUS_RATE_LIMIT_PER_MINUTE": "0"},
        toolchain_fn=lambda: None,
    )

    assert report["ready"] is False
    assert report["state"] == "PILOT_NOT_READY"
    assert set(report["blockers"]) == {
        "durable_state_store",
        "durable_idempotency_journal",
        "no_ambiguous_idempotency_side_effects",
        "native_cpp20_toolchain",
        "api_key_guard",
        "request_rate_limit",
    }


def test_tampered_evidence_ledger_is_a_hard_pilot_blocker(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_evidence(kind="test", subject="fixture", payload={"ok": True})
    with store._lock, store._connection:  # intentional white-box corruption fixture
        store._connection.execute("UPDATE evidence_ledger SET entry_hash = ? WHERE sequence = 1", ("f" * 64,))

    report = build_pilot_readiness(
        store=store,
        journal=_journal(tmp_path),
        environment={
            "MORPHEUS_API_KEY": "pilot-secret-with-more-than-24-chars",
            "MORPHEUS_RATE_LIMIT_PER_MINUTE": "60",
        },
        toolchain_fn=_toolchain,
    )

    assert report["ready"] is False
    assert "evidence_ledger_integrity" in report["blockers"]
    check = next(item for item in report["checks"] if item["id"] == "evidence_ledger_integrity")
    assert check["evidence_state"] == "PILOT_EVIDENCE_LEDGER_INVALID"


def test_invalid_rate_limit_text_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    report = build_pilot_readiness(
        store=store,
        journal=_journal(tmp_path),
        environment={
            "MORPHEUS_API_KEY": "pilot-secret-with-more-than-24-chars",
            "MORPHEUS_RATE_LIMIT_PER_MINUTE": "many",
        },
        toolchain_fn=_toolchain,
    )
    assert report["ready"] is False
    assert "request_rate_limit" in report["blockers"]


def test_ambiguous_idempotency_record_blocks_preflight_without_corrupting_journal() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as raw:
        tmp_path = Path(raw)
        with _journal(tmp_path) as journal:
            digest = "a" * 64
            claim = journal.claim(operation="fixture", key="pilot-readiness-key-0001", request_digest=digest)
            journal.mark_ambiguous_failure(
                operation="fixture",
                key_sha256=claim.key_sha256,
                request_digest=digest,
            )

            report = build_pilot_readiness(
                store=_store(tmp_path),
                journal=journal,
                environment={
                    "MORPHEUS_API_KEY": "pilot-secret-with-more-than-24-chars",
                    "MORPHEUS_RATE_LIMIT_PER_MINUTE": "60",
                },
                toolchain_fn=_toolchain,
            )
            integrity = next(item for item in report["checks"] if item["id"] == "durable_idempotency_journal")
            ambiguous = next(item for item in report["checks"] if item["id"] == "no_ambiguous_idempotency_side_effects")
            assert integrity["passed"] is True
            assert ambiguous["passed"] is False
            assert ambiguous["evidence_state"] == "PILOT_AMBIGUOUS_IDEMPOTENCY_SIDE_EFFECTS_BLOCKING"
            assert "no_ambiguous_idempotency_side_effects" in report["blockers"]
            assert report["ready"] is False


def test_pending_idempotency_operations_are_visible_as_advisory_only(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.claim(operation="fixture", key="pilot-pending-key-0001", request_digest="b" * 64)
    report = build_pilot_readiness(
        store=_store(tmp_path),
        journal=journal,
        environment={
            "MORPHEUS_API_KEY": "pilot-secret-with-more-than-24-chars",
            "MORPHEUS_RATE_LIMIT_PER_MINUTE": "60",
        },
        toolchain_fn=_toolchain,
    )
    assert report["ready"] is True
    assert "pending_idempotency_operations" in report["advisories"]
