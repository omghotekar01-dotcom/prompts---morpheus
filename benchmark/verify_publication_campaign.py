#!/usr/bin/env python3
"""Fail-closed verifier for MORPHEUS publication benchmark campaign manifests.

This intentionally checks the integrity-critical subset without third-party dependencies.
It is designed to run in CI before benchmark results are accepted for publication claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(data: dict[str, Any], *, repo_root: Path | None = None) -> None:
    required = {
        "campaign_id",
        "git_commit",
        "machine_profile_sha256",
        "workload_manifest_sha256",
        "compiler",
        "environment_controls",
        "random_seed",
        "warmup_iterations",
        "measurement_repetitions",
        "claim_scope",
        "raw_output_path",
    }
    missing = sorted(required - data.keys())
    _require(not missing, f"missing required fields: {', '.join(missing)}")

    _require(isinstance(data["campaign_id"], str) and data["campaign_id"].strip(), "campaign_id must be non-empty")
    _require(isinstance(data["git_commit"], str) and GIT_SHA_RE.fullmatch(data["git_commit"]) is not None, "git_commit must be a full 40-char lowercase Git SHA")

    for field in ("machine_profile_sha256", "workload_manifest_sha256"):
        value = data[field]
        _require(isinstance(value, str) and SHA256_RE.fullmatch(value) is not None, f"{field} must be lowercase SHA-256")

    compiler = data["compiler"]
    _require(isinstance(compiler, dict), "compiler must be an object")
    for field in ("name", "version", "flags"):
        _require(field in compiler, f"compiler.{field} is required")
    _require(isinstance(compiler["flags"], list) and all(isinstance(v, str) for v in compiler["flags"]), "compiler.flags must be a string list")

    controls = data["environment_controls"]
    _require(isinstance(controls, dict) and controls, "environment_controls must be a non-empty object")

    seed = data["random_seed"]
    _require(type(seed) is int and seed >= 0, "random_seed must be a non-negative integer")

    warmups = data["warmup_iterations"]
    repetitions = data["measurement_repetitions"]
    _require(type(warmups) is int and warmups >= 1, "warmup_iterations must be >= 1")
    _require(type(repetitions) is int and repetitions >= 10, "measurement_repetitions must be >= 10")

    claims = data["claim_scope"]
    _require(isinstance(claims, dict), "claim_scope must be an object")
    allowed = claims.get("allowed", [])
    forbidden = claims.get("forbidden", [])
    _require(isinstance(allowed, list) and all(isinstance(v, str) and v.strip() for v in allowed), "claim_scope.allowed must be a non-empty-string list")
    _require(isinstance(forbidden, list) and all(isinstance(v, str) and v.strip() for v in forbidden), "claim_scope.forbidden must be a non-empty-string list")
    _require(set(allowed).isdisjoint(forbidden), "claim_scope.allowed and forbidden must not overlap")

    raw_output = data["raw_output_path"]
    _require(isinstance(raw_output, str) and raw_output.strip(), "raw_output_path must be non-empty")
    if repo_root is not None:
        resolved = (repo_root / raw_output).resolve()
        _require(repo_root.resolve() in resolved.parents or resolved == repo_root.resolve(), "raw_output_path must stay inside repository root")

    # Optional file bindings: when provided, verify bytes rather than trusting metadata.
    bindings = data.get("artifact_bindings", {})
    _require(isinstance(bindings, dict), "artifact_bindings must be an object")
    if repo_root is not None:
        for name, binding in bindings.items():
            _require(isinstance(binding, dict), f"artifact_bindings.{name} must be an object")
            rel = binding.get("path")
            expected = binding.get("sha256")
            _require(isinstance(rel, str) and rel, f"artifact_bindings.{name}.path is required")
            _require(isinstance(expected, str) and SHA256_RE.fullmatch(expected) is not None, f"artifact_bindings.{name}.sha256 must be SHA-256")
            path = (repo_root / rel).resolve()
            _require(repo_root.resolve() in path.parents or path == repo_root.resolve(), f"artifact_bindings.{name}.path escapes repository")
            _require(path.is_file(), f"artifact_bindings.{name}.path does not exist")
            _require(_sha256_file(path) == expected, f"artifact_bindings.{name} hash mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--repo-root", type=Path, default=None)
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        _require(isinstance(data, dict), "manifest root must be an object")
        verify_manifest(data, repo_root=args.repo_root)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"REJECTED: {exc}")
        return 2
    print("VERIFIED: publication campaign manifest passed integrity checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
