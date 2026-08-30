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

from app.idempotency import JOURNAL  # noqa: E402
from app.pilot_idempotency_resolution import resolve_idempotency_ambiguity  # noqa: E402
from app.storage import STORE  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect or manually resolve MORPHEUS ambiguous pilot idempotency records. "
            "No command automatically retries a request."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="List unresolved ambiguity identities from the local journal.")
    listing.add_argument("--limit", type=int, default=50)

    resolve = sub.add_parser("resolve", help="Apply one evidence-audited manual resolution.")
    resolve.add_argument("--operation", required=True)
    resolve.add_argument("--key-sha256", required=True)
    resolve.add_argument("--request-sha256", required=True)
    resolve.add_argument(
        "--outcome",
        required=True,
        choices=["CONFIRMED_NO_SIDE_EFFECT", "CONFIRMED_SIDE_EFFECT_PRESENT"],
    )
    resolve.add_argument("--operator", required=True, dest="operator_id")
    resolve.add_argument(
        "--reason-file",
        required=True,
        type=Path,
        help="UTF-8 incident rationale. The text is read locally but only its SHA-256 is persisted.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "list":
            rows = JOURNAL.list_unresolved_ambiguities(limit=args.limit)
            result = {
                "schema": "morpheus-idempotency-unresolved-list-v1",
                "count": len(rows),
                "records": rows,
                "truth_boundary": "Only hashed request/key identities are shown. This command performs no resolution or retry.",
            }
        else:
            reason = args.reason_file.read_text(encoding="utf-8")
            result = resolve_idempotency_ambiguity(
                store=STORE,
                journal=JOURNAL,
                operation=args.operation,
                key_sha256=args.key_sha256,
                request_sha256=args.request_sha256,
                outcome=args.outcome,
                operator_id=args.operator_id,
                reason=reason,
            )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        print(
            json.dumps(
                {
                    "schema": "morpheus-idempotency-operator-command-error-v1",
                    "command": args.command,
                    "state": "FAILED_CLOSED",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
