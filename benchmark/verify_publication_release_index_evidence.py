"""CLI: independently verify a MORPHEUS release index against exact bundle evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmark.publication_catalog_release_index import verify_release_index_against_bundles


def _load_object(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("bundles", type=Path, nargs="+", help="two or more release bundle JSON files")
    args = parser.parse_args()
    try:
        index = _load_object(args.index)
        bundles = tuple(_load_object(path) for path in args.bundles)
        verified = verify_release_index_against_bundles(index, bundles)
        result = {
            "verified": True,
            "schema": verified.schema,
            "source_revision": verified.source_revision,
            "release_count": len(verified.release_digests),
            "total_claim_count": verified.total_claim_count,
            "index_digest": verified.index_digest,
            "production_deployment_authorized": False,
        }
        print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"verified": False, "error": str(exc), "production_deployment_authorized": False}, sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
