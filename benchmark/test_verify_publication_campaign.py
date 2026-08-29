from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("verify_publication_campaign.py")
SPEC = importlib.util.spec_from_file_location("verify_publication_campaign", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
verify_manifest = MODULE.verify_manifest


def valid_manifest() -> dict:
    return {
        "schema_version": "1.0", "campaign_id": "morpheus-rq3-campaign-001", "git_commit": "a" * 40,
        "machine_profile_sha256": "b" * 64, "workload_manifest_sha256": "c" * 64,
        "compiler": {"name": "clang++", "version": "18.1.0", "flags": ["-O3", "-DNDEBUG"]},
        "build_mode": "release", "repetitions": 30, "warmup_repetitions": 3, "random_seed": 17,
        "environment": {"os": "Ubuntu 24.04", "cpu_governor": "performance", "affinity_policy": "pinned-core-set", "background_load_policy": "benchmark-host-idle", "clock_source": "steady_clock", "turbo_policy": "disabled", "thermal_policy": "steady-state-before-run"},
        "claim_scope": {"allowed": ["software benchmark latency"], "forbidden": ["hardware energy"]},
        "raw_output_directory": "benchmark/raw/campaign-001",
    }


class PublicationCampaignVerifierTests(unittest.TestCase):
    def test_accepts_minimal_valid_manifest(self) -> None:
        verify_manifest(valid_manifest())

    def test_rejects_boolean_seed_even_though_bool_is_int_subclass(self) -> None:
        manifest = valid_manifest(); manifest["random_seed"] = True
        with self.assertRaisesRegex(ValueError, "random_seed"): verify_manifest(manifest)

    def test_rejects_claim_overlap(self) -> None:
        manifest = valid_manifest(); manifest["claim_scope"]["forbidden"].append("software benchmark latency")
        with self.assertRaisesRegex(ValueError, "must not overlap"): verify_manifest(manifest)

    def test_rejects_raw_output_escape_without_repo_root(self) -> None:
        manifest = valid_manifest(); manifest["raw_output_directory"] = "../outside"
        with self.assertRaisesRegex(ValueError, "must not contain"): verify_manifest(manifest)

    def test_rejects_absolute_raw_output_without_repo_root(self) -> None:
        manifest = valid_manifest(); manifest["raw_output_directory"] = "/tmp/morpheus-evidence"
        with self.assertRaisesRegex(ValueError, "repository-relative"): verify_manifest(manifest)

    def test_artifact_binding_verifies_actual_bytes(self) -> None:
        manifest = valid_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); artifact = root / "benchmark" / "raw" / "evidence.bin"; artifact.parent.mkdir(parents=True); artifact.write_bytes(b"morpheus-evidence")
            manifest["artifact_bindings"] = {"raw_evidence": {"path": "benchmark/raw/evidence.bin", "sha256": MODULE.hashlib.sha256(b"morpheus-evidence").hexdigest()}}
            verify_manifest(manifest, repo_root=root)
            tampered = copy.deepcopy(manifest); tampered["artifact_bindings"]["raw_evidence"]["sha256"] = "d" * 64
            with self.assertRaisesRegex(ValueError, "hash mismatch"): verify_manifest(tampered, repo_root=root)

    def test_rejects_all_zero_artifact_hash_without_repo_root(self) -> None:
        manifest = valid_manifest(); manifest["artifact_bindings"] = {"raw_evidence": {"path": "benchmark/raw/evidence.bin", "sha256": "0" * 64}}
        with self.assertRaisesRegex(ValueError, "all-zero"): verify_manifest(manifest)

    def test_rejects_noncanonical_artifact_binding_key(self) -> None:
        manifest = valid_manifest(); manifest["artifact_bindings"] = {" raw_evidence ": {"path": "benchmark/raw/evidence.bin", "sha256": "d" * 64}}
        with self.assertRaisesRegex(ValueError, "canonical"): verify_manifest(manifest)

    def test_rejects_artifact_path_escape_without_repo_root(self) -> None:
        manifest = valid_manifest(); manifest["artifact_bindings"] = {"raw_evidence": {"path": "../outside.bin", "sha256": "d" * 64}}
        with self.assertRaisesRegex(ValueError, "must not contain"): verify_manifest(manifest)

    def test_rejects_absolute_artifact_path_without_repo_root(self) -> None:
        manifest = valid_manifest(); manifest["artifact_bindings"] = {"raw_evidence": {"path": "/tmp/outside.bin", "sha256": "d" * 64}}
        with self.assertRaisesRegex(ValueError, "repository-relative"): verify_manifest(manifest)


if __name__ == "__main__": unittest.main()
