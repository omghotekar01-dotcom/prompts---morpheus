from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web_hosting import mount_web_app, resolve_web_dist


def test_web_hosting_is_disabled_when_build_is_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MORPHEUS_WEB_DIST", str(tmp_path / "missing"))
    monkeypatch.chdir(tmp_path)
    assert resolve_web_dist() is None
    assert mount_web_app(FastAPI(), tmp_path / "missing") is False


def test_web_hosting_serves_spa_and_assets_without_shadowing_api(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>MORPHEUS DEPLOY</body></html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('morpheus')", encoding="utf-8")

    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    assert mount_web_app(app, dist) is True
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok"}
    root = client.get("/")
    assert root.status_code == 200
    assert "MORPHEUS DEPLOY" in root.text
    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "morpheus" in asset.text
