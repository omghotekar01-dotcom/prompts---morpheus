from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_pilot.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("morpheus_run_pilot_test_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_never_starts_server_when_preflight_is_blocked(monkeypatch) -> None:
    module = _load_script()
    called = []
    monkeypatch.setattr(
        module,
        "build_pilot_readiness",
        lambda: {
            "ready": False,
            "blockers": ["api_key_guard"],
            "advisories": [],
            "readiness_sha256": "a" * 64,
        },
    )
    monkeypatch.setattr(module.uvicorn, "run", lambda *args, **kwargs: called.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    assert module.main() == 3
    assert called == []


def test_launcher_starts_exactly_one_worker_after_green_preflight(monkeypatch) -> None:
    module = _load_script()
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        module,
        "build_pilot_readiness",
        lambda: {
            "ready": True,
            "blockers": [],
            "advisories": [],
            "readiness_sha256": "b" * 64,
        },
    )
    monkeypatch.setattr(module.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    assert module.main() == 0
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("app.server:app",)
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8000
    assert kwargs["workers"] == 1
    assert kwargs["reload"] is False


def test_launcher_rejects_non_loopback_before_preflight_without_acknowledgement(monkeypatch) -> None:
    module = _load_script()
    preflight_called = []
    monkeypatch.setattr(module, "build_pilot_readiness", lambda: preflight_called.append(True) or {"ready": True})
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--host", "0.0.0.0"])

    assert module.main() == 2
    assert preflight_called == []
