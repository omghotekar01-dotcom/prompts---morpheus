from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


ARTIFACT = "a" * 64
MANIFEST = "b" * 64


def test_gated_migration_api_requires_verification_then_commits_and_rolls_back() -> None:
    client = TestClient(app)
    session_id = "api-migration-session"
    migration_id = "api-migration"

    started = client.post(
        "/api/runtime/sessions",
        json={
            "session_id": session_id,
            "active_candidate_id": "candidate-a",
            "baseline": {
                "operation_mix": {"point_lookup": 0.9, "range_scan": 0.1},
                "expected_future_queries": 100000,
                "sequence": 0,
            },
            "drift_threshold": 0.2,
            "cooldown_windows": 0,
        },
    )
    assert started.status_code == 200

    observed = client.post(
        f"/api/runtime/sessions/{session_id}/observe",
        json={
            "snapshot": {
                "operation_mix": {"point_lookup": 0.1, "range_scan": 0.9},
                "expected_future_queries": 100000,
                "sequence": 1,
            },
            "alternative_candidate_id": "candidate-b",
            "current_predicted_latency_us": 10,
            "alternative_predicted_latency_us": 2,
            "estimated_switching_cost_us": 1000,
        },
    )
    assert observed.status_code == 200
    assert observed.json()["decision"]["action"] == "SWITCH_RECOMMENDED"

    planned = client.post(
        f"/api/runtime/sessions/{session_id}/migrations/plan",
        json={"migration_id": migration_id},
    )
    assert planned.status_code == 200
    assert planned.json()["state"] == "PLANNED"

    early_commit = client.post(f"/api/runtime/sessions/{session_id}/migrations/{migration_id}/commit")
    assert early_commit.status_code == 422

    shadow = client.post(
        f"/api/migrations/{migration_id}/shadow",
        json={"artifact_sha256": ARTIFACT},
    )
    assert shadow.status_code == 200
    assert shadow.json()["state"] == "SHADOW_BUILT"

    verified = client.post(
        f"/api/migrations/{migration_id}/verify",
        json={
            "compile_verified": True,
            "correctness_verified": True,
            "verification_manifest_sha256": MANIFEST,
        },
    )
    assert verified.status_code == 200
    assert verified.json()["state"] == "VERIFIED"

    committed = client.post(f"/api/runtime/sessions/{session_id}/migrations/{migration_id}/commit")
    assert committed.status_code == 200
    assert committed.json()["migration"]["state"] == "COMMITTED"
    assert committed.json()["runtime"]["active_candidate_id"] == "candidate-b"

    rolled_back = client.post(
        f"/api/runtime/sessions/{session_id}/migrations/{migration_id}/rollback",
        json={"reason": "post-commit health gate failed"},
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["migration"]["state"] == "ROLLED_BACK"
    assert rolled_back.json()["runtime"]["active_candidate_id"] == "candidate-a"
