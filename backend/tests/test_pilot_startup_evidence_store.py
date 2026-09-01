from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pilot_startup_evidence_store import PilotStartupEvidenceStore


DIGEST = "a" * 64


def _receipt() -> dict[str, object]:
    return {
        "schema": "morpheus-pilot-startup-evidence-v1",
        "evidence_state": "BOUND_VERIFIED_SINGLE_NODE_PILOT_STARTUP_INPUTS",
        "source_revision": "b" * 40,
        "capability_sha256": "c" * 64,
        "readiness_sha256": "d" * 64,
        "launch_plan_sha256": "e" * 64,
        "fingerprints": {
            "api_contract_sha256": "f" * 64,
            "feature_policy_sha256": "1" * 64,
        },
        "production_deployment_authorized": False,
        "truth_boundaries": [
            "This receipt is a deterministic SHA-256 content binding, not a digital signature or external attestation.",
            "It binds startup-control evidence for the declared single-node engineering pilot only.",
            "It does not establish production authorization, a security certification, an SLA, customer validation, performance superiority, publication acceptance, novelty or patentability.",
        ],
        "startup_evidence_sha256": DIGEST,
    }


def test_persist_and_load_verified_receipt(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: payload == _receipt())
    store = PilotStartupEvidenceStore(tmp_path)
    target = store.persist(_receipt())
    assert target.name == f"{DIGEST}.json"
    assert store.load(DIGEST) == _receipt()
    assert target.read_text(encoding="utf-8").endswith("\n")


def test_persist_is_idempotent_for_identical_verified_content(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: payload == _receipt())
    store = PilotStartupEvidenceStore(tmp_path)
    first = store.persist(_receipt())
    second = store.persist(_receipt())
    assert first == second


def test_persist_rejects_unverified_or_authority_widened_receipt(monkeypatch, tmp_path: Path) -> None:
    store = PilotStartupEvidenceStore(tmp_path)
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: False)
    with pytest.raises(ValueError, match="failed verification"):
        store.persist(_receipt())

    widened = _receipt()
    widened["production_deployment_authorized"] = True
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: True)
    with pytest.raises(ValueError, match="deny production deployment"):
        store.persist(widened)


def test_existing_path_with_different_bytes_fails_closed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: payload == _receipt())
    store = PilotStartupEvidenceStore(tmp_path)
    target = store.path_for(DIGEST)
    tmp_path.mkdir(parents=True, exist_ok=True)
    target.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="collision or on-disk tampering"):
        store.persist(_receipt())


def test_load_rejects_filename_mismatch_and_noncanonical_json(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: payload == _receipt())
    store = PilotStartupEvidenceStore(tmp_path)
    other = "2" * 64
    store.path_for(other).write_text(json.dumps(_receipt()), encoding="utf-8")
    with pytest.raises(ValueError, match="filename does not match"):
        store.load(other)

    store.path_for(DIGEST).write_text(json.dumps(_receipt(), indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="not canonical JSON"):
        store.load(DIGEST)


def test_path_for_rejects_path_traversal_and_malformed_digests(tmp_path: Path) -> None:
    store = PilotStartupEvidenceStore(tmp_path)
    for value in ("../x", "A" * 64, "a" * 63, "g" * 64):
        with pytest.raises(ValueError, match="digest must"):
            store.path_for(value)
