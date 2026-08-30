from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.server import app


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = (REPO_ROOT / "examples" / "users-demo.yaml").read_text(encoding="utf-8")
client = TestClient(app)


def _request(key: str, *, spec_text: str = SPEC):
    return client.post(
        "/api/v2/pilot/synthesize",
        headers={"Idempotency-Key": key},
        json={"spec_text": spec_text, "strategy": "auto"},
    )


def test_pilot_synthesis_replays_same_run_for_same_key_and_request() -> None:
    key = f"pilot-test-{uuid.uuid4().hex}"
    first = _request(key)
    assert first.status_code == 200
    assert first.headers["idempotency-replayed"] == "false"
    assert len(first.headers["x-morpheus-idempotency-key-sha256"]) == 64
    first_payload = first.json()
    assert first_payload["run_id"]
    assert first_payload["pilot_contract"]["scope"] == "SINGLE_NODE_DURABLE_IDEMPOTENCY"

    second = _request(key)
    assert second.status_code == 200
    assert second.headers["idempotency-replayed"] == "true"
    second_payload = second.json()
    assert second_payload == first_payload
    assert second_payload["run_id"] == first_payload["run_id"]


def test_same_idempotency_key_cannot_be_reused_for_different_request() -> None:
    key = f"pilot-conflict-{uuid.uuid4().hex}"
    first = _request(key)
    assert first.status_code == 200

    changed = SPEC.replace("users_demo", "users_demo_changed", 1)
    conflict = _request(key, spec_text=changed)
    assert conflict.status_code == 409
    assert conflict.json()["evidence_state"] == "IDEMPOTENCY_KEY_REQUEST_CONFLICT"


def test_pilot_synthesis_requires_explicit_idempotency_key() -> None:
    response = client.post(
        "/api/v2/pilot/synthesize",
        json={"spec_text": SPEC, "strategy": "auto"},
    )
    assert response.status_code == 422
