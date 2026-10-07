from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_SOURCE = ROOT / "frontend" / "src" / "api.ts"
PILOT_SOURCE = ROOT / "frontend" / "src" / "pilotSynthesis.ts"


def test_browser_synthesis_uses_durable_pilot_contract() -> None:
    api = API_SOURCE.read_text(encoding="utf-8")
    helper = PILOT_SOURCE.read_text(encoding="utf-8")

    assert "request<SynthesisResult>('/api/v2/pilot/synthesize'" in api
    assert "'Idempotency-Key': idempotencyKey" in api
    assert "pilotSynthesisRequestIdentity(payload)" in api
    assert "clearPilotSynthesisRetry(idempotencyKey)" in api

    assert "morpheus-pilot-synthesis-retry-v1" in helper
    assert "window.sessionStorage" in helper
    assert "window.crypto.randomUUID" in helper
    assert "window.crypto.subtle.digest('SHA-256'" in helper


def test_browser_synthesis_does_not_use_legacy_non_idempotent_route() -> None:
    api = API_SOURCE.read_text(encoding="utf-8")
    synthesize_block = api.split("export async function synthesize(", 1)[1].split(
        "export function verifyArtifact(", 1
    )[0]

    assert "'/api/synthesize'" not in synthesize_block
