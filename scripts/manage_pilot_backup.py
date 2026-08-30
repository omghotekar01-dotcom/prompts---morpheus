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
from app.pilot_backup import create_pilot_backup, restore_pilot_backup, verify_pilot_backup  # noqa: E402
from app.storage import STORE  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create, verify, or isolated-restore a MORPHEUS single-node pilot recovery checkpoint."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a new content-hashed recovery checkpoint.")
    create.add_argument("output", type=Path, help="New backup directory; must not already exist.")

    verify = subparsers.add_parser("verify", help="Verify backup manifest, bytes, and SQLite structure.")
    verify.add_argument("backup", type=Path)

    restore = subparsers.add_parser("restore", help="Restore into a new isolated state directory and verify it.")
    restore.add_argument("backup", type=Path)
    restore.add_argument("target", type=Path, help="New restore directory; must not already exist.")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "create":
            result = create_pilot_backup(store=STORE, journal=JOURNAL, output_dir=args.output)
        elif args.command == "verify":
            result = verify_pilot_backup(args.backup)
        else:
            result = restore_pilot_backup(args.backup, target_state_dir=args.target)
    except (OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "schema": "morpheus-pilot-backup-command-error-v1",
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
