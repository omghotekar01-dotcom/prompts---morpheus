from __future__ import annotations

from .advanced_api import router as advanced_router
from .hardening_api import router as hardening_router
from .main import app
from .operational_metrics import RequestObservabilityMiddleware
from .research_api import router as research_router

# Keep the mature v1 routes stable while adding versioned evidence-safe surfaces.
# This module is the canonical server entrypoint from MORPHEUS v0.10 onward.
app.include_router(advanced_router)
app.include_router(research_router)
app.include_router(hardening_router)
app.add_middleware(RequestObservabilityMiddleware)
