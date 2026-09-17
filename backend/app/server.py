from __future__ import annotations

from .advanced_api import router as advanced_router
from .hardening_api import router as hardening_router
from .main import app
from .operational_metrics import RequestObservabilityMiddleware
from .pilot_api import router as pilot_router
from .pilot_cors import PilotCorsMiddleware
from .research_api import router as research_router
from .startup_mvp_api import router as startup_mvp_router
from .web_hosting import mount_web_app

# Keep the mature v1 routes stable while adding versioned evidence-safe surfaces.
# This module is the canonical server entrypoint from MORPHEUS v0.10 onward.
app.include_router(advanced_router)
app.include_router(research_router)
app.include_router(hardening_router)
app.include_router(pilot_router)
app.include_router(startup_mvp_router)
app.add_middleware(RequestObservabilityMiddleware)
app.add_middleware(PilotCorsMiddleware)

# When a production frontend build exists (Docker/single-service deployment), serve
# it from the same origin as the API. Local Vite development remains unchanged.
mount_web_app(app)
