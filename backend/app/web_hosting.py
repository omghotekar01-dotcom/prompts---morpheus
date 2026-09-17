from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def resolve_web_dist() -> Path | None:
    """Return a usable built frontend directory when one is configured/present."""
    configured = os.environ.get("MORPHEUS_WEB_DIST")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(Path(__file__).resolve().parents[2] / "frontend" / "dist")
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved.is_dir() and (resolved / "index.html").is_file()):
            return resolved
    return None


def mount_web_app(app: FastAPI, dist_dir: Path | None = None) -> bool:
    """Serve the production React build from FastAPI without shadowing /api routes.

    The mount is intentionally performed after API routers are registered. Assets are
    immutable build output; the root route serves the SPA entrypoint. MORPHEUS does
    not claim this local/single-node hosting mode is HA or multi-tenant production.
    """
    dist = dist_dir.resolve() if dist_dir is not None else resolve_web_dist()
    if dist is None or not dist.is_dir() or not (dist / "index.html").is_file():
        return False

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="web-assets")

    @app.get("/", include_in_schema=False)
    def morpheus_web_root() -> FileResponse:
        return FileResponse(dist / "index.html")

    return True
