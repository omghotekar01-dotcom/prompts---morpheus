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


def test_launcher_never_runs_preflight_when_capability_ledger_is_invalid(monkeypatch) -> None:
    module = _load_script()
    preflight_called = []
    server_called = []
    capabilities = {"sha256": "c" * 64, "production_deployment_authorized": False}
    monkeypatch.setattr(module, "pilot_capabilities_payload", lambda: capabilities)
    monkeypatch.setattr(module, "verify_pilot_capabilities", lambda payload: False)
    monkeypatch.setattr(module, "build_pilot_readiness", lambda: preflight_called.append(True) or {"ready": True})
    monkeypatch.setattr(module.uvicorn, "run", lambda *args, **kwargs: server_called.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    assert module.main() == 3
    assert preflight_called == []
    assert server_called == []


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
    monkeypatch.setattr(module, "verify_pilot_readiness", lambda report: True)
    monkeypatch.setattr(module.uvicorn, "run", lambda *args, **kwargs: called.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    assert module.main() == 3
    assert called == []


def test_launcher_never_starts_server_when_readiness_receipt_is_invalid(monkeypatch) -> None:
    module = _load_script()
    called = []
    monkeypatch.setattr(
        module,
        "build_pilot_readiness",
        lambda: {
            "ready": True,
            "blockers": [],
            "advisories": [],
            "readiness_sha256": "f" * 64,
        },
    )
    monkeypatch.setattr(module, "verify_pilot_readiness", lambda report: False)
    monkeypatch.setattr(module.uvicorn, "run", lambda *args, **kwargs: called.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    assert module.main() == 3
    assert called == []


def test_launcher_starts_exactly_one_worker_after_verified_green_preflight(monkeypatch, tmp_path: Path) -> None:
    module = _load_script()
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    persisted: list[tuple[object, Path]] = []
    readiness = {
        "ready": True,
        "blockers": [],
        "advisories": [],
        "readiness_sha256": "b" * 64,
    }
    startup_evidence = {
        "source_revision": "a" * 40,
        "startup_evidence_sha256": "c" * 64,
        "fingerprints": {"feature_policy_sha256": "d" * 64},
        "production_deployment_authorized": False,
    }
    evidence_dir = tmp_path / "startup-evidence"
    monkeypatch.setattr(module, "build_pilot_readiness", lambda: readiness)
    monkeypatch.setattr(module, "verify_pilot_readiness", lambda report: report is readiness)
    monkeypatch.setattr(module, "_resolve_source_revision", lambda: "a" * 40)
    monkeypatch.setattr(module, "_build_verified_startup_evidence", lambda **kwargs: startup_evidence)
    monkeypatch.setattr(
        module,
        "_persist_verified_startup_evidence",
        lambda evidence, root: persisted.append((evidence, root)) or root / f"{evidence['startup_evidence_sha256']}.json",
    )
    monkeypatch.setattr(module.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--startup-evidence-dir", str(evidence_dir)])

    assert module.main() == 0
    assert persisted == [(startup_evidence, evidence_dir)]
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("app.server:app",)
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8000
    assert kwargs["workers"] == 1
    assert kwargs["reload"] is False


def test_launcher_fails_closed_when_verified_startup_evidence_cannot_be_persisted(monkeypatch, tmp_path: Path) -> None:
    module = _load_script()
    server_called = []
    readiness = {
        "ready": True,
        "blockers": [],
        "advisories": [],
        "readiness_sha256": "b" * 64,
    }
    startup_evidence = {
        "source_revision": "a" * 40,
        "startup_evidence_sha256": "c" * 64,
        "fingerprints": {"feature_policy_sha256": "d" * 64},
        "production_deployment_authorized": False,
    }
    monkeypatch.setattr(module, "build_pilot_readiness", lambda: readiness)
    monkeypatch.setattr(module, "verify_pilot_readiness", lambda report: report is readiness)
    monkeypatch.setattr(module, "_resolve_source_revision", lambda: "a" * 40)
    monkeypatch.setattr(module, "_build_verified_startup_evidence", lambda **kwargs: startup_evidence)

    def fail_persistence(evidence, root):
        raise OSError("read-only evidence volume")

    monkeypatch.setattr(module, "_persist_verified_startup_evidence", fail_persistence)
    monkeypatch.setattr(module.uvicorn, "run", lambda *args, **kwargs: server_called.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--startup-evidence-dir", str(tmp_path / "readonly")])

    assert module.main() == 3
    assert server_called == []


def test_launcher_rejects_non_loopback_before_preflight_without_acknowledgement(monkeypatch) -> None:
    module = _load_script()
    preflight_called = []
    monkeypatch.setattr(module, "build_pilot_readiness", lambda: preflight_called.append(True) or {"ready": True})
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--host", "0.0.0.0"])

    assert module.main() == 2
    assert preflight_called == []
