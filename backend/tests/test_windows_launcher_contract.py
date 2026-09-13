from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_windows_launcher_selects_verified_dynamic_ports() -> None:
    launcher = (ROOT / "START-MORPHEUS.ps1").read_text(encoding="utf-8")

    assert "Get-AvailablePort 8000 8099" in launcher
    assert "Get-AvailablePort 5173 5273" in launcher
    assert "Wait-ForEndpoint \"$BackendUrl/api/health\"" in launcher
    assert "MORPHEUS_BACKEND_URL" in launcher
    assert "MORPHEUS_FRONTEND_PORT" in launcher
    assert "--host 127.0.0.1 --port $BackendPort" in launcher
    assert "--reload" not in launcher
    assert "--port 8000" not in launcher


def test_vite_proxy_uses_launcher_selected_backend() -> None:
    config = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")

    assert "MORPHEUS_BACKEND_URL" in config
    assert "MORPHEUS_FRONTEND_PORT" in config
    assert "target: backendTarget" in config
    assert "strictPort: true" in config


def test_startup_progress_represents_ready_checks_not_failed_completion() -> None:
    startup = (ROOT / "frontend" / "src" / "StartupGate.tsx").read_text(encoding="utf-8")

    assert "Math.round((ready / steps.length) * 100)" in startup
    assert "ready · {completed}/{steps.length} checked" in startup
    assert "MORPHEUS backend is unavailable" in startup
