from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_packaged_runtime_is_non_root_and_does_not_trust_arbitrary_forwarded_headers() -> None:
    dockerfile = _read("Dockerfile")

    assert "useradd --create-home --uid 10001" in dockerfile
    assert "USER morpheus" in dockerfile
    assert "MORPHEUS_STATE_DIR=/data" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "--forwarded-allow-ips=*" not in dockerfile
    assert "--proxy-headers" not in dockerfile


def test_guarded_environment_example_contains_no_committed_secret() -> None:
    example = _read(".env.example")
    gitignore = _read(".gitignore")

    assert "MORPHEUS_API_KEY=\n" in example
    assert "MORPHEUS_RATE_LIMIT_PER_MINUTE=120" in example
    assert ".env\n" in gitignore
    assert "!.env.example" in gitignore


def test_ci_has_a_guarded_container_smoke_after_main_build_matrix() -> None:
    workflow = _read(".github/workflows/ci.yml")

    assert "Container / guarded single-node smoke" in workflow
    assert "needs: [backend, backend-windows, core, core-windows, core-sanitizers, frontend]" in workflow
    assert "-p 127.0.0.1:18000:8000" in workflow
    assert "--read-only" in workflow
    assert "--cap-drop ALL" in workflow
    assert "--security-opt no-new-privileges" in workflow
    assert "docker compose config" in workflow
    assert "/api/v2/ai/status" in workflow
    assert "startup_mvp_percent" in workflow
    assert 'test "$(docker exec morpheus-ci id -u)" = "10001"' in workflow


def test_deployment_doc_does_not_present_packaged_smoke_as_production_proof() -> None:
    deployment = _read("DEPLOYMENT.md")

    assert "127.0.0.1:8000:8000" in deployment
    assert "Control-plane key" in deployment
    assert "production_deployment_authorized: false" in deployment
    assert "automatic_control_allowed: false" in deployment
    assert "not an external production" in deployment.lower()


def test_compose_profile_is_loopback_non_root_hardened_and_stateful() -> None:
    compose = _read("compose.yaml")

    assert '127.0.0.1:8000:8000' in compose
    assert 'read_only: true' in compose
    assert 'no-new-privileges:true' in compose
    assert 'cap_drop:' in compose and '- ALL' in compose
    assert 'morpheus-state:/data' in compose
    assert 'host.docker.internal:host-gateway' in compose
    assert 'restart: unless-stopped' in compose


def test_environment_example_keeps_ai_optional_and_server_configured() -> None:
    example = _read(".env.example")

    assert "MORPHEUS_AI_PROVIDER=disabled" in example
    assert "MORPHEUS_AI_MODEL=" in example
    assert "MORPHEUS_AI_BASE_URL=" in example
    assert "MORPHEUS_AI_API_KEY=" in example
    assert "MORPHEUS_AI_TIMEOUT_SECONDS=20" in example
    assert "MORPHEUS_DOMAIN=" in example


def test_public_pilot_profile_puts_morpheus_behind_tls_ingress() -> None:
    compose = _read("compose.public.yaml")
    caddy = _read("deploy/Caddyfile")

    assert 'expose:' in compose and '"8000"' in compose
    assert '127.0.0.1:8000:8000' not in compose
    assert '"80:80"' in compose
    assert '"443:443"' in compose
    assert 'MORPHEUS_DOMAIN:' in compose
    assert 'read_only: true' in compose
    assert 'no-new-privileges:true' in compose
    assert 'reverse_proxy morpheus:8000' in caddy
    assert 'Strict-Transport-Security "max-age=31536000"' in caddy
    assert 'X-Robots-Tag "noindex, nofollow, noarchive"' in caddy
