from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from release.build_release_manifest import build_manifest


COMMIT = "a" * 40
SHA = "b" * 64
SPEEDUP_ROLES = [
    "experiment_manifest",
    "raw_measurements",
    "statistical_summary",
    "machine_profile",
    "baseline_manifest",
]


def test_claim_cannot_self_authorize_by_declaring_absent_evidence_roles() -> None:
    manifest = build_manifest(
        {
            "version": "0.10.0-rc1",
            "commit": COMMIT,
            "artifacts": [],
            "claims": [
                {
                    "type": "measured_speedup",
                    "text": "Declared roles alone must not authorize this claim.",
                    "evidence_roles": SPEEDUP_ROLES,
                }
            ],
        }
    )
    assert manifest["schema"] == "morpheus-release-manifest-v2"
    assert manifest["release_state"] == "BLOCKED_BY_CLAIM_EVIDENCE"
    decision = manifest["claim_gate"]["decisions"][0]
    assert set(decision["missing_roles"]) == set(SPEEDUP_ROLES)
    assert set(manifest["claims"][0]["declared_roles_missing_from_artifacts"]) == set(SPEEDUP_ROLES)


def test_actual_manifest_artifact_roles_satisfy_structural_claim_role_gate() -> None:
    manifest = build_manifest(
        {
            "version": "0.10.0-rc1",
            "commit": COMMIT,
            "artifacts": [{"role": role, "sha256": SHA} for role in SPEEDUP_ROLES],
            "claims": [
                {
                    "type": "measured_speedup",
                    "text": "The claim role bundle is structurally complete.",
                    "evidence_roles": SPEEDUP_ROLES,
                }
            ],
        }
    )
    assert manifest["release_state"] == "CLAIMS_EVIDENCE_COMPLETE"
    assert manifest["claim_gate"]["decisions"][0]["missing_roles"] == []
    assert manifest["claims"][0]["declared_roles_missing_from_artifacts"] == []
    assert set(manifest["available_evidence_roles"]) == set(SPEEDUP_ROLES)
