"""CLI for independently verifying MORPHEUS publication release indexes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from benchmark.publication_catalog_release_index import verify_release_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MORPHEUS publication catalog release index JSON file.")
    parser.add_argument("index", type=Path, help="Path to the serialized release index JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        raw = json.loads(args.index.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("release index root must be a JSON object")
        verified = verify_release_index(raw)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1

    print(json.dumps({
        "ok": True,
        "schema": verified.schema,
        "source_revision": verified.source_revision,
        "release_count": len(verified.release_digests),
        "total_claim_count": verified.total_claim_count,
        "index_digest": verified.index_digest,
        "production_deployment_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
