#!/usr/bin/env python3
"""Fail-closed verifier for MORPHEUS publication benchmark campaign manifests.

The verifier mirrors ``publication_campaign.schema.json`` using only the standard
library, then adds integrity checks the schema cannot express: zero/placeholder
provenance rejection, contradictory claim detection, duplicate compiler flags,
and optional artifact-byte verification.
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
CAMPAIGN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
ZERO_SHA256 = "0" * 64
ZERO_GIT_SHA = "0" * 40
PLACEHOLDER_MARKERS = ("replace_", "placeholder", "template only")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be non-empty text")
    return value.strip()


def _not_placeholder(value: str, field: str) -> None:
    lowered = value.casefold()
    _require(not any(marker in lowered for marker in PLACEHOLDER_MARKERS), f"{field} contains a placeholder")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_repo_path(repo_root: Path, raw: str, field: str) -> Path:
    rel = Path(raw)
    _require(not rel.is_absolute(), f"{field} must be repository-relative")
    _require(".." not in rel.parts, f"{field} must not contain '..'")
    root = repo_root.resolve()
    resolved = (root / rel).resolve()
    _require(resolved == root or root in resolved.parents, f"{field} escapes repository root")
    return resolved


def verify_manifest(data: dict[str, Any], *, repo_root: Path | None = None) -> None:
    required = {
        "schema_version",
        "campaign_id",
        "git_commit",
        "machine_profile_sha256",
        "workload_manifest_sha256",
        "compiler",
        "build_mode",
        "repetitions",
        "warmup_repetitions",
        "random_seed",
        "environment",
        "claim_scope",
    }
    allowed_top_level = required | {"raw_output_directory", "notes", "artifact_bindings"}
    missing = sorted(required - data.keys())
    unknown = sorted(data.keys() - allowed_top_level)
    _require(not missing, f"missing required fields: {', '.join(missing)}")
    _require(not unknown, f"unknown fields: {', '.join(unknown)}")
    _require(data["schema_version"] == "1.0", "schema_version must be '1.0'")

    campaign_id = _text(data["campaign_id"], "campaign_id")
    _require(8 <= len(campaign_id) <= 128, "campaign_id length must be 8..128")
    _require(CAMPAIGN_ID_RE.fullmatch(campaign_id) is not None, "campaign_id contains unsupported characters")

    git_commit = data["git_commit"]
    _require(isinstance(git_commit, str) and GIT_SHA_RE.fullmatch(git_commit) is not None, "git_commit must be a full 40-char lowercase Git SHA")
    _require(git_commit != ZERO_GIT_SHA, "git_commit cannot be an all-zero placeholder")

    for field in ("machine_profile_sha256", "workload_manifest_sha256"):
        value = data[field]
        _require(isinstance(value, str) and SHA256_RE.fullmatch(value) is not None, f"{field} must be lowercase SHA-256")
        _require(value != ZERO_SHA256, f"{field} cannot be an all-zero placeholder")

    compiler = data["compiler"]
    _require(isinstance(compiler, dict), "compiler must be an object")
    _require(set(compiler) <= {"name", "version", "flags"}, "compiler contains unknown fields")
    for field in ("name", "version", "flags"):
        _require(field in compiler, f"compiler.{field} is required")
    compiler_name = _text(compiler["name"], "compiler.name")
    compiler_version = _text(compiler["version"], "compiler.version")
    _not_placeholder(compiler_name, "compiler.name")
    _not_placeholder(compiler_version, "compiler.version")
    flags = compiler["flags"]
    _require(isinstance(flags, list) and all(isinstance(v, str) for v in flags), "compiler.flags must be a string list")
    _require(len(flags) == len(set(flags)), "compiler.flags must not contain duplicates")

    _require(data["build_mode"] in {"release", "relwithdebinfo"}, "build_mode must be release or relwithdebinfo")
    repetitions = data["repetitions"]
    warmups = data["warmup_repetitions"]
    seed = data["random_seed"]
    _require(type(repetitions) is int and repetitions >= 10, "repetitions must be an integer >= 10")
    _require(type(warmups) is int and warmups >= 1, "warmup_repetitions must be an integer >= 1")
    _require(type(seed) is int and seed >= 0, "random_seed must be a non-negative integer")

    environment = data["environment"]
    required_env = {"os", "cpu_governor", "affinity_policy", "background_load_policy", "clock_source"}
    optional_env = {"turbo_policy", "thermal_policy"}
    _require(isinstance(environment, dict), "environment must be an object")
    _require(required_env <= environment.keys(), "environment is missing required controls")
    _require(set(environment) <= required_env | optional_env, "environment contains unknown fields")
    for field in required_env:
        value = _text(environment[field], f"environment.{field}")
        _not_placeholder(value, f"environment.{field}")
    for field in optional_env & environment.keys():
        if environment[field]:
            _not_placeholder(_text(environment[field], f"environment.{field}"), f"environment.{field}")

    claims = data["claim_scope"]
    _require(isinstance(claims, dict), "claim_scope must be an object")
    _require(set(claims) == {"allowed", "forbidden"}, "claim_scope must contain only allowed and forbidden")
    allowed = claims["allowed"]
    forbidden = claims["forbidden"]
    _require(isinstance(allowed, list) and allowed and all(isinstance(v, str) and v.strip() for v in allowed), "claim_scope.allowed must be a non-empty-string list")
    _require(isinstance(forbidden, list) and forbidden and all(isinstance(v, str) and v.strip() for v in forbidden), "claim_scope.forbidden must be a non-empty-string list")
    allowed_normalized = {v.strip().casefold() for v in allowed}
    forbidden_normalized = {v.strip().casefold() for v in forbidden}
    _require(allowed_normalized.isdisjoint(forbidden_normalized), "claim_scope.allowed and forbidden must not overlap")

    raw_output = data.get("raw_output_directory")
    if raw_output is not None:
        raw_output = _text(raw_output, "raw_output_directory")
        if repo_root is not None:
            _safe_repo_path(repo_root, raw_output, "raw_output_directory")

    notes = data.get("notes")
    if notes is not None:
        _require(isinstance(notes, str), "notes must be a string")
        _not_placeholder(notes, "notes")

    bindings = data.get("artifact_bindings", {})
    _require(isinstance(bindings, dict), "artifact_bindings must be an object")
    for name, binding in bindings.items():
        binding_name = _text(name, "artifact_bindings key")
        _require(binding_name == name, "artifact_bindings keys must be canonical non-whitespace text")
        _require(isinstance(binding, dict), f"artifact_bindings.{name} must be an object")
        _require(set(binding) == {"path", "sha256"}, f"artifact_bindings.{name} must contain path and sha256")
        rel = _text(binding["path"], f"artifact_bindings.{name}.path")
        expected = binding["sha256"]
        _require(isinstance(expected, str) and SHA256_RE.fullmatch(expected) is not None, f"artifact_bindings.{name}.sha256 must be SHA-256")
        _require(expected != ZERO_SHA256, f"artifact_bindings.{name}.sha256 cannot be all-zero")
        if repo_root is not None:
            path = _safe_repo_path(repo_root, rel, f"artifact_bindings.{name}.path")
            _require(path.is_file(), f"artifact_bindings.{name}.path does not exist")
            _require(_sha256_file(path) == expected, f"artifact_bindings.{name} hash mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify MORPHEUS publication benchmark provenance")
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
