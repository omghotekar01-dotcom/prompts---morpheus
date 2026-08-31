#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import uvicorn  # noqa: E402

from app.feature_registry import feature_registry_fingerprint  # noqa: E402
from app.hardening_api import openapi_contract_fingerprint  # noqa: E402
from app.pilot_capabilities import pilot_capabilities_payload  # noqa: E402
from app.pilot_capabilities_verifier import verify_pilot_capabilities  # noqa: E402
from app.pilot_launch import build_pilot_launch_plan  # noqa: E402
from app.pilot_readiness import build_pilot_readiness  # noqa: E402
from app.pilot_readiness_verifier import verify_pilot_readiness  # noqa: E402
from app.pilot_startup_evidence import (  # noqa: E402
    build_pilot_startup_evidence,
    verify_pilot_startup_evidence,
)
from app.server import app as pilot_app  # noqa: E402

_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Start the MORPHEUS single-node engineering pilot only after fail-closed capability, readiness, "
            "and startup-evidence gates pass. The launcher always uses exactly one application worker."
        )
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--allow-network-bind",
        action="store_true",
        help=(
            "Acknowledge an explicit non-loopback bind. This does not add TLS, identity, a gateway/WAF, tenancy, "
            "or production authorization."
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=("critical", "error", "warning", "info", "debug", "trace"),
        default="info",
    )
    return parser


def _emit(payload: dict[str, object], *, stream=None) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2), file=stream or sys.stdout)


def _resolve_source_revision() -> str:
    """Resolve the exact repository HEAD without invoking a command shell."""

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("unable to resolve repository source revision") from exc

    revision = completed.stdout.strip().lower()
    if completed.returncode != 0 or _GIT_REVISION.fullmatch(revision) is None:
        raise RuntimeError("unable to resolve canonical repository source revision")
    return revision


def _api_contract_fingerprint() -> str:
    """Fingerprint the exact FastAPI route contract that the pilot will launch."""

    _, fingerprint = openapi_contract_fingerprint(pilot_app.openapi())
    return fingerprint


def _build_verified_startup_evidence(
    *,
    capabilities: Mapping[str, Any],
    readiness: Mapping[str, Any],
    launch_plan: Mapping[str, Any],
    source_revision: str,
) -> dict[str, Any]:
    """Build and independently verify the pilot startup content binding."""

    evidence = build_pilot_startup_evidence(
        capabilities=capabilities,
        readiness=readiness,
        launch_plan=launch_plan,
        source_revision=source_revision,
        api_contract_sha256=_api_contract_fingerprint(),
        feature_policy_sha256=feature_registry_fingerprint(),
    )
    if not verify_pilot_startup_evidence(evidence):
        raise RuntimeError("pilot startup evidence failed independent verification")
    return evidence


def main() -> int:
    args = _parser().parse_args()
    try:
        plan = build_pilot_launch_plan(
            host=args.host,
            port=args.port,
            allow_network_bind=args.allow_network_bind,
        )
    except ValueError as exc:
        _emit(
            {
                "schema": "morpheus-pilot-launch-error-v1",
                "state": "INVALID_LAUNCH_PLAN",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            stream=sys.stderr,
        )
        return 2

    capabilities = pilot_capabilities_payload()
    if not verify_pilot_capabilities(capabilities):
        _emit(
            {
                "schema": "morpheus-pilot-launch-blocked-v1",
                "state": "PILOT_CAPABILITY_LEDGER_INVALID",
                "capability_sha256": capabilities.get("sha256"),
                "launch_plan_sha256": plan.sha256,
                "production_deployment_authorized": False,
            },
            stream=sys.stderr,
        )
        return 3

    try:
        readiness = build_pilot_readiness()
    except Exception as exc:
        _emit(
            {
                "schema": "morpheus-pilot-launch-error-v1",
                "state": "PREFLIGHT_INTERNAL_FAILURE",
                "error_type": type(exc).__name__,
                "truth_boundary": "Startup failed closed; exception text is omitted because it may contain local configuration detail.",
            },
            stream=sys.stderr,
        )
        return 2

    if not verify_pilot_readiness(readiness):
        _emit(
            {
                "schema": "morpheus-pilot-launch-blocked-v1",
                "state": "PILOT_READINESS_RECEIPT_INVALID",
                "blockers": [],
                "advisories": [],
                "readiness_sha256": readiness.get("readiness_sha256"),
                "capability_sha256": capabilities.get("sha256"),
                "launch_plan_sha256": plan.sha256,
                "production_deployment_authorized": False,
            },
            stream=sys.stderr,
        )
        return 3

    if readiness.get("ready") is not True:
        _emit(
            {
                "schema": "morpheus-pilot-launch-blocked-v1",
                "state": "PILOT_NOT_READY",
                "blockers": readiness.get("blockers", []),
                "advisories": readiness.get("advisories", []),
                "readiness_sha256": readiness.get("readiness_sha256"),
                "capability_sha256": capabilities.get("sha256"),
                "launch_plan_sha256": plan.sha256,
                "production_deployment_authorized": False,
            },
            stream=sys.stderr,
        )
        return 3

    try:
        source_revision = _resolve_source_revision()
        startup_evidence = _build_verified_startup_evidence(
            capabilities=capabilities,
            readiness=readiness,
            launch_plan=plan.as_dict(),
            source_revision=source_revision,
        )
    except Exception as exc:
        _emit(
            {
                "schema": "morpheus-pilot-launch-blocked-v1",
                "state": "PILOT_STARTUP_EVIDENCE_INVALID",
                "error_type": type(exc).__name__,
                "readiness_sha256": readiness.get("readiness_sha256"),
                "capability_sha256": capabilities.get("sha256"),
                "launch_plan_sha256": plan.sha256,
                "production_deployment_authorized": False,
                "truth_boundary": "Startup evidence failed closed; exception text is omitted because it may contain local repository detail.",
            },
            stream=sys.stderr,
        )
        return 3

    _emit(
        {
            "schema": "morpheus-pilot-launch-start-v1",
            "state": "STARTING_SINGLE_NODE_PILOT",
            "source_revision": startup_evidence["source_revision"],
            "startup_evidence_sha256": startup_evidence["startup_evidence_sha256"],
            "readiness_sha256": readiness.get("readiness_sha256"),
            "capability_sha256": capabilities.get("sha256"),
            "api_contract_sha256": startup_evidence["fingerprints"].get("api_contract_sha256"),
            "feature_policy_sha256": startup_evidence["fingerprints"].get("feature_policy_sha256"),
            "production_deployment_authorized": False,
            "launch_plan": plan.as_dict(),
        }
    )
    try:
        uvicorn.run(
            "app.server:app",
            host=plan.host,
            port=plan.port,
            workers=1,
            reload=False,
            log_level=args.log_level,
        )
    except (OSError, RuntimeError) as exc:
        _emit(
            {
                "schema": "morpheus-pilot-launch-error-v1",
                "state": "SERVER_START_FAILURE",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "production_deployment_authorized": False,
            },
            stream=sys.stderr,
        )
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
