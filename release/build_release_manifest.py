#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.claim_gate import evaluate_claim_bundle


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic release manifest whose claim gate uses actual artifacts.

    Claim entries may document the evidence roles an author intended to cite, but
    they cannot self-authorize a claim by merely naming missing roles. The gate
    is evaluated from artifact roles physically present in the manifest input.
    """

    version = str(payload.get("version", "")).strip()
    commit = str(payload.get("commit", "")).strip().lower()
    if not version:
        raise ValueError("version is required")
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise ValueError("commit must be a 40-character hexadecimal git SHA")

    artifacts = payload.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("artifacts must be an array")
    roles: dict[str, list[str]] = {}
    normalized_artifacts: list[dict[str, str]] = []
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError("artifact entries must be objects")
        role = str(item.get("role", "")).strip()
        sha256 = str(item.get("sha256", "")).strip().lower()
        if not role:
            raise ValueError("artifact role cannot be empty")
        if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
            raise ValueError(f"artifact {role!r} has invalid sha256")
        normalized_artifacts.append({"role": role, "sha256": sha256})
        roles.setdefault(role, []).append(sha256)

    available_roles = frozenset(roles)
    claims_raw = payload.get("claims", [])
    if not isinstance(claims_raw, list):
        raise ValueError("claims must be an array")
    claims: list[dict[str, Any]] = []
    bundle_inputs: list[tuple[str, frozenset[str]]] = []
    for item in claims_raw:
        if not isinstance(item, dict):
            raise ValueError("claim entries must be objects")
        claim_type = str(item.get("type", "")).strip()
        text = str(item.get("text", "")).strip()
        if not text:
            raise ValueError("claim text cannot be empty")
        declared_roles = sorted(set(str(role).strip() for role in item.get("evidence_roles", []) if str(role).strip()))
        declared_missing = sorted(set(declared_roles) - available_roles)
        # The authority input is the manifest's actual artifact-role set, never
        # the claim author's role list. This closes a fail-open path where a
        # claim could previously name evidence that was not packaged.
        bundle_inputs.append((claim_type, available_roles))
        claims.append(
            {
                "type": claim_type,
                "text": text,
                "evidence_roles_declared": declared_roles,
                "declared_roles_missing_from_artifacts": declared_missing,
            }
        )

    claim_gate = evaluate_claim_bundle(bundle_inputs)
    manifest_core = {
        "schema": "morpheus-release-manifest-v2",
        "version": version,
        "commit": commit,
        "artifacts": sorted(normalized_artifacts, key=lambda item: (item["role"], item["sha256"])),
        "available_evidence_roles": sorted(available_roles),
        "claims": claims,
        "claim_gate": claim_gate,
        "truth_boundaries": [
            "A release manifest records byte-identity evidence references; it does not manufacture measurements.",
            "Claim gates use roles of artifacts actually present in this manifest; a claim cannot self-authorize by naming absent evidence.",
            "Patentability, legal freedom-to-operate, and universal performance superiority are outside this manifest's authority.",
        ],
    }
    manifest_hash = hashlib.sha256(_canonical_json(manifest_core).encode("utf-8")).hexdigest()
    return {
        **manifest_core,
        "manifest_sha256": manifest_hash,
        "release_state": "CLAIMS_EVIDENCE_COMPLETE" if claim_gate["allowed"] else "BLOCKED_BY_CLAIM_EVIDENCE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a claim-gated MORPHEUS release manifest from JSON input.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("release input must be a JSON object")
        manifest = build_manifest(payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"morpheus release manifest: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0 if manifest["release_state"] == "CLAIMS_EVIDENCE_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
