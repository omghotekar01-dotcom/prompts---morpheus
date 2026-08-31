#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import uvicorn  # noqa: E402

from app.pilot_launch import build_pilot_launch_plan  # noqa: E402
from app.pilot_readiness import build_pilot_readiness  # noqa: E402
from app.pilot_readiness_verifier import verify_pilot_readiness  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Start the MORPHEUS single-node engineering pilot only after the fail-closed readiness gate passes. "
            "The launcher always uses exactly one application worker."
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
                "launch_plan_sha256": plan.sha256,
                "production_deployment_authorized": False,
            },
            stream=sys.stderr,
        )
        return 3

    _emit(
        {
            "schema": "morpheus-pilot-launch-start-v1",
            "state": "STARTING_SINGLE_NODE_PILOT",
            "readiness_sha256": readiness.get("readiness_sha256"),
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
