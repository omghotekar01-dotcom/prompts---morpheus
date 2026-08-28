from __future__ import annotations

from .advanced_api import router as advanced_router
from .main import app
from .research_api import router as research_router

# Keep the mature v1 routes stable while adding v2 evidence-safe surfaces.
# This module is the canonical server entrypoint from MORPHEUS v0.10 onward.
app.include_router(advanced_router)
app.include_router(research_router)
