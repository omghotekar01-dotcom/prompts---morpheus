from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_pilot.py"
SPEC = importlib.util.spec_from_file_location("morpheus_run_pilot", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
run_pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_pilot)


def test_source_revision_resolution_uses_no_shell_and_requires_canonical_head(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="a" * 40 + "\n", stderr="")

    monkeypatch.setattr(run_pilot.subprocess, "run", fake_run)
    assert run_pilot._resolve_source_revision() == "a" * 40
    assert calls[0]["command"] == ["git", "rev-parse", "--verify", "HEAD"]
    assert "shell" not in calls[0]
    assert calls[0]["cwd"] == run_pilot.REPO_ROOT
    assert calls[0]["timeout"] == 5


@pytest.mark.parametrize(
    "returncode, stdout",
    [
        (1, ""),
        (0, "abc1234\n"),
        (0, "g" * 40 + "\n"),
        (0, "a" * 41 + "\n"),
    ],
)
def test_source_revision_resolution_fails_closed_on_noncanonical_identity(monkeypatch, returncode: int, stdout: str) -> None:
    monkeypatch.setattr(
        run_pilot.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr="failed"),
    )
    with pytest.raises(RuntimeError, match="source revision"):
        run_pilot._resolve_source_revision()


def test_source_revision_resolution_fails_closed_when_git_cannot_execute(monkeypatch) -> None:
    def explode(command, **kwargs):
        raise OSError("git unavailable")

    monkeypatch.setattr(run_pilot.subprocess, "run", explode)
    with pytest.raises(RuntimeError, match="source revision"):
        run_pilot._resolve_source_revision()


def test_api_contract_fingerprint_uses_exact_launched_app_contract(monkeypatch) -> None:
    document = {"paths": {"/health": {"get": {}}}}
    monkeypatch.setattr(run_pilot.pilot_app, "openapi", lambda: document)
    monkeypatch.setattr(
        run_pilot,
        "openapi_contract_fingerprint",
        lambda value: ({"schema": "test", "paths": {}}, "e" * 64) if value is document else (_ for _ in ()).throw(AssertionError()),
    )
    assert run_pilot._api_contract_fingerprint() == "e" * 64


def test_launcher_evidence_helper_binds_api_contract_feature_policy_and_independently_verifies(monkeypatch) -> None:
    observed: dict[str, object] = {}
    receipt = {
        "source_revision": "b" * 40,
        "startup_evidence_sha256": "c" * 64,
        "fingerprints": {
            "api_contract_sha256": "e" * 64,
            "feature_policy_sha256": "d" * 64,
        },
        "production_deployment_authorized": False,
    }

    def fake_build(**kwargs):
        observed.update(kwargs)
        return receipt

    monkeypatch.setattr(run_pilot, "_api_contract_fingerprint", lambda: "e" * 64)
    monkeypatch.setattr(run_pilot, "feature_registry_fingerprint", lambda: "d" * 64)
    monkeypatch.setattr(run_pilot, "build_pilot_startup_evidence", fake_build)
    monkeypatch.setattr(run_pilot, "verify_pilot_startup_evidence", lambda payload: payload is receipt)

    capabilities = {"sha256": "a" * 64, "production_deployment_authorized": False}
    readiness = {"readiness_sha256": "b" * 64, "ready": True}
    launch_plan = {"sha256": "c" * 64, "production_deployment_authorized": False}

    result = run_pilot._build_verified_startup_evidence(
        capabilities=capabilities,
        readiness=readiness,
        launch_plan=launch_plan,
        source_revision="b" * 40,
    )

    assert result is receipt
    assert observed == {
        "capabilities": capabilities,
        "readiness": readiness,
        "launch_plan": launch_plan,
        "source_revision": "b" * 40,
        "api_contract_sha256": "e" * 64,
        "feature_policy_sha256": "d" * 64,
    }


def test_launcher_evidence_helper_fails_closed_when_independent_verification_rejects(monkeypatch) -> None:
    monkeypatch.setattr(run_pilot, "_api_contract_fingerprint", lambda: "e" * 64)
    monkeypatch.setattr(run_pilot, "feature_registry_fingerprint", lambda: "d" * 64)
    monkeypatch.setattr(
        run_pilot,
        "build_pilot_startup_evidence",
        lambda **kwargs: {"startup_evidence_sha256": "c" * 64},
    )
    monkeypatch.setattr(run_pilot, "verify_pilot_startup_evidence", lambda payload: False)

    with pytest.raises(RuntimeError, match="independent verification"):
        run_pilot._build_verified_startup_evidence(
            capabilities={},
            readiness={},
            launch_plan={},
            source_revision="b" * 40,
        )
