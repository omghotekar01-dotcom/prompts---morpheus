from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Keep tests reproducible whether pytest is invoked from the repository root,
# backend/, an IDE, or GitHub Actions.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def _reset_active_calibration():
    from app.calibration import CALIBRATIONS

    CALIBRATIONS.deactivate()
    yield
    CALIBRATIONS.deactivate()
