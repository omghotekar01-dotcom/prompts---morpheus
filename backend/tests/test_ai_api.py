from __future__ import annotations

import json

from fastapi.testclient import TestClient

import app.ai_api as ai_api
import app.advanced_api as advanced_api
from app.server import app


class FakeProvider:
    def __init__(self, *, draft_payload: dict[str, object] | None = None, fail: bool = False) -> None:
        self.draft_payload = draft_payload or {}
        self.fail = fail

    def public_status(self) -> dict[str, object]:
        return {
            "configured": True,
            "provider": "ollama",
            "base_url": "http://127.0.0.1:11434",
            "model": "test-model",
            "api_key_configured": False,
            "timeout_seconds": 5.0,
            "evidence_authority": False,
            "automatic_control_authority": False,
            "mode": "OPTIONAL_LANGUAGE_PROVIDER_NO_EVIDENCE_AUTHORITY",
        }

    def complete_json(self, _prompt: str) -> str:
        if self.fail:
            raise RuntimeError("provider unavailable")
        return '{"status":"ok"}'

    def complete_text(self, messages, *, temperature=0.1, max_tokens=1200) -> str:
        if self.fail:
            from app.ai_provider import AIProviderError

            raise AIProviderError("configured AI provider request failed")
        system = messages[0]["content"]
        if "Rewrite the supplied MORPHEUS evidence answer" in system:
            return "AI wording of deterministic evidence."
        return json.dumps(self.draft_payload)


VALID_AI_DRAFT = {
    "mws_yaml": """version: mws-0.1
name: ai_draft
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
  memory_mb: 32
objective:
  latency: 1.0
  memory: 0.1
  update: 0.1
  build: 0.05
""",
    "assumptions": ["Used 1000 records because the description omitted scale."],
}


def test_ai_status_is_safe_when_disabled(monkeypatch) -> None:
    monkeypatch.delenv("MORPHEUS_AI_PROVIDER", raising=False)
    response = TestClient(app).get("/api/v2/ai/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert payload["evidence_authority"] is False
    assert payload["automatic_control_authority"] is False


def test_ai_workload_draft_is_deterministically_validated(monkeypatch) -> None:
    provider = FakeProvider(draft_payload=VALID_AI_DRAFT)
    monkeypatch.setattr(ai_api, "configured_ai_provider", lambda: provider)

    response = TestClient(app).post(
        "/api/v2/ai/workload-draft",
        json={"description": "Create a point-lookup workload keyed by id."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validated"] is True
    assert payload["attempts"] == 1
    assert payload["evidence_state"] == "AI_DRAFT_VALIDATED_MWS_USER_REVIEW_REQUIRED"
    assert payload["eligible_for_runtime_automatic_control"] is False
    assert payload["provider"]["evidence_authority"] is False
    assert "name: ai_draft" in payload["draft_spec_text"]


def test_ai_workload_draft_rejects_invalid_base_before_provider_call(monkeypatch) -> None:
    provider = FakeProvider(draft_payload=VALID_AI_DRAFT)
    monkeypatch.setattr(ai_api, "configured_ai_provider", lambda: provider)

    response = TestClient(app).post(
        "/api/v2/ai/workload-draft",
        json={
            "description": "Modify the workload.",
            "base_spec_text": "version: mws-0.1\nqueries: []\n",
        },
    )

    assert response.status_code == 422
    assert "base_spec_text is invalid" in response.json()["detail"]


def test_ai_probe_reports_connectivity_without_upgrading_authority(monkeypatch) -> None:
    provider = FakeProvider()
    monkeypatch.setattr(ai_api, "configured_ai_provider", lambda: provider)

    response = TestClient(app).post("/api/v2/ai/test")
    assert response.status_code == 200
    payload = response.json()
    assert payload["reachable"] is True
    assert payload["provider"]["automatic_control_authority"] is False
    assert "no evidence" in payload["truth_boundary"].lower()


def test_copilot_keeps_deterministic_answer_authoritative_when_ai_is_enabled(monkeypatch) -> None:
    spec = """version: mws-0.1
name: copilot_ai_test
record_count: 100
fields:
  - name: id
    type: uint64
queries:
  - kind: point_lookup
    field: id
"""
    client = TestClient(app)
    synthesis = client.post("/api/synthesize", json={"spec_text": spec, "strategy": "auto"})
    assert synthesis.status_code == 200
    run_id = synthesis.json()["run_id"]
    provider = FakeProvider()
    monkeypatch.setattr(advanced_api, "configured_ai_provider", lambda: provider)

    response = TestClient(app).post(
        "/api/v2/copilot/explain",
        json={"run_id": run_id, "question": "Why did this design win?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["authoritative_answer"]
    assert payload["answer"] == payload["authoritative_answer"]
    assert payload["ai_rendered_answer"] == "AI wording of deterministic evidence."
    assert payload["ai_provider"]["evidence_authority"] is False
    assert any("presentation-only" in item for item in payload["limitations"])


def test_copilot_falls_back_when_ai_provider_fails(monkeypatch) -> None:
    from app.ai_provider import AIProviderError

    monkeypatch.setattr(advanced_api, "configured_ai_provider", lambda: (_ for _ in ()).throw(AIProviderError("bad config")))
    client = TestClient(app)
    spec = """version: mws-0.1
name: fallback_ai_test
record_count: 100
fields:
  - name: id
    type: uint64
queries:
  - kind: point_lookup
    field: id
"""
    synthesis = client.post("/api/synthesize", json={"spec_text": spec, "strategy": "auto"})
    assert synthesis.status_code == 200

    response = client.post(
        "/api/v2/copilot/explain",
        json={"run_id": synthesis.json()["run_id"], "question": "What evidence exists?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["authoritative_answer"]
    assert payload["ai_rendered_answer"] is None
    assert payload["ai_fallback"] == "bad config"
