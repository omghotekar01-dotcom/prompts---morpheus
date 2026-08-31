"""Command-line verifier for MORPHEUS publication catalog release bundles.

Usage:
    python -m benchmark.verify_publication_catalog_release_cli bundle.json

The command is deliberately standard-library-only and emits machine-readable
JSON so independent reviewers can validate release evidence without importing
producer-side tooling.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from benchmark.publication_catalog_release_bundle import verify_release_bundle


def verify_file(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"release bundle file not found: {source}") from exc
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"release bundle file cannot be read: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"release bundle is not valid JSON: {exc.msg}") from exc
    if not isinstance(raw, dict):
        raise ValueError("release bundle root must be a JSON object")

    verified = verify_release_bundle(raw)
    return {
        "valid": True,
        "schema": verified.schema,
        "source_revision": verified.source_revision,
        "release_digest": verified.release_digest,
        "claim_count": verified.claim_count,
        "manifest_count": len(verified.manifest_digests),
        "production_deployment_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(json.dumps({"valid": False, "error": "usage: verify_publication_catalog_release_cli <bundle.json>"}, sort_keys=True))
        return 2
    try:
        result = verify_file(args[0])
    except ValueError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
