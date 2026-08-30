from __future__ import annotations

from pathlib import Path

from app.pilot_readiness import build_pilot_readiness
from app.storage import StateStore
from app.toolchain import Toolchain


def _toolchain() -> Toolchain:
    return Toolchain(kind="gnu", executable="/opt/test/g++", version="g++ test 1")


def _store(tmp_path: Path) -> StateStore:
    return StateStore(db_path=tmp_path / "state.db", artifact_root=tmp_path / "artifacts")


def test_guarded_single_node_pilot_can_be_ready_without_active_calibration(tmp_path: Path) -> None:
    store = _store(tmp_path)
    report = build_pilot_readiness(
        store=store,
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
    assert any("not a security certification" in item for item in report["truth_boundaries"])


def test_unprotected_ephemeral_process_fails_pilot_readiness(tmp_path: Path) -> None:
    store = StateStore(db_path=":memory:", artifact_root=tmp_path / "artifacts")
    report = build_pilot_readiness(
        store=store,
        environment={"MORPHEUS_RATE_LIMIT_PER_MINUTE": "0"},
        toolchain_fn=lambda: None,
    )

    assert report["ready"] is False
    assert report["state"] == "PILOT_NOT_READY"
    assert set(report["blockers"]) == {
        "durable_state_store",
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
        environment={
            "MORPHEUS_API_KEY": "pilot-secret-with-more-than-24-chars",
            "MORPHEUS_RATE_LIMIT_PER_MINUTE": "many",
        },
        toolchain_fn=_toolchain,
    )
    assert report["ready"] is False
    assert "request_rate_limit" in report["blockers"]
