from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Keep tests reproducible whether pytest is invoked from the repository root,
# backend/, an IDE, or GitHub Actions.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Import-time isolation matters because app.storage constructs the global STORE
# as modules are imported. Force every pytest run into a temporary state root so
# local tests can never add calibration profiles, runs, artifacts or ledger
# entries to the operator's real ~/.morpheus database.
_TEST_STATE_ROOT = Path(tempfile.mkdtemp(prefix="morpheus-pytest-state-")).resolve()
os.environ["MORPHEUS_STATE_DIR"] = str(_TEST_STATE_ROOT)
os.environ["MORPHEUS_DB_PATH"] = str(_TEST_STATE_ROOT / "test.db")
os.environ["MORPHEUS_ARTIFACT_DIR"] = str(_TEST_STATE_ROOT / "artifacts")
atexit.register(lambda: shutil.rmtree(_TEST_STATE_ROOT, ignore_errors=True))


@pytest.fixture(autouse=True)
def _reset_active_calibration():
    from app.calibration import CALIBRATIONS

    CALIBRATIONS.deactivate(persist=False)
    yield
    CALIBRATIONS.deactivate(persist=False)
