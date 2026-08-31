"""Standalone CLI for independently verifying MORPHEUS publication claims.

Usage:
    python -m benchmark.verify_publication_claims_cli manifest.json

The command consumes only serialized JSON and the independent verifier. It
prints a machine-readable success record to stdout and sends validation errors
to stderr with a non-zero exit code.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from benchmark.publication_claim_verifier import (
    PublicationClaimVerificationError,
    verify_publication_claim_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="morpheus-verify-publication-claims",
        description="Independently verify a serialized MORPHEUS publication-claim manifest.",
    )
    parser.add_argument("manifest", type=Path, help="Path to the exported manifest JSON file")
    return parser


def _load_manifest(path: Path) -> object:
    if not path.is_file():
        raise PublicationClaimVerificationError(f"manifest file does not exist: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PublicationClaimVerificationError(f"unable to read manifest: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PublicationClaimVerificationError(
            f"manifest is not valid JSON at line {exc.lineno} column {exc.colno}"
        ) from exc


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = _load_manifest(args.manifest)
        digest = verify_publication_claim_manifest(manifest)
    except PublicationClaimVerificationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "ok": True,
                "schema": "morpheus.publication_claim_verification.v1",
                "manifest_sha256": digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
