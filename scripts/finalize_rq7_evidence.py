#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (REPO_ROOT, BACKEND_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.generated_migration_campaign_io import load_generated_migration_campaign  # noqa: E402
from app.release_evidence_validation import validate_release_evidence_bytes  # noqa: E402
from app.rq7_analysis_provenance import ANALYSIS_SOURCE_PATH, build_rq7_analysis_provenance  # noqa: E402
from app.rq7_confirmatory_analysis import analyze_rq7_confirmatory  # noqa: E402
from app.rq7_record_count_effect_evidence import build_rq7_record_count_effect_evidence  # noqa: E402
from release.evidence_package import build_evidence_package  # noqa: E402


_REQUIRED_RUN_FILES = {
    "experiment_manifest": "generated-migration-experiment-manifest.json",
    "machine_profile": "generated-migration-machine-profile.json",
    "generated_migration_campaign": "generated-migration-campaign.json",
    "generated_migration_campaign_summary": "generated-migration-summary.json",
    "generated_migration_transition_cost_evidence": "generated-migration-transition-cost-evidence.json",
    "measurement_environment_record": "generated-migration-measurement-environment.json",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _artifact(path: Path, role: str) -> dict[str, str]:
    data = path.read_bytes()
    return {"role": role, "path": str(path.resolve()), "sha256": _sha256_bytes(data)}


def _validate_run_artifact(role: str, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required RQ7 artifact is missing: {path}")
    data = path.read_bytes()
    structural = validate_release_evidence_bytes(role, data)
    if not structural.valid:
        raise ValueError(f"invalid {role}: {'; '.join(structural.details)}")
    payload = _load_json_object(path, label=role)
    return payload


def _measurement_commit(machine_profile: dict[str, Any]) -> str:
    commit = str(machine_profile.get("source_commit", "")).strip().lower()
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise ValueError("RQ7 machine profile must contain the 40-hex measurement source_commit")
    return commit


def finalize_rq7_evidence(
    run_dir: Path,
    output_dir: Path,
    *,
    version: str,
    zip_output: Path | None = None,
) -> dict[str, Any]:
    version = version.strip()
    if not version:
        raise ValueError("version is required")
    run_dir = run_dir.resolve()
    output_dir = output_dir.resolve()
    if not run_dir.is_dir():
        raise ValueError(f"RQ7 run directory does not exist: {run_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {role: run_dir / filename for role, filename in _REQUIRED_RUN_FILES.items()}
    payloads = {role: _validate_run_artifact(role, path) for role, path in paths.items()}

    campaign_payload = payloads["generated_migration_campaign"]
    campaign = load_generated_migration_campaign(campaign_payload)
    analysis = analyze_rq7_confirmatory(campaign)
    analysis_path = output_dir / "rq7-confirmatory-analysis.json"
    _write_json_atomic(analysis_path, analysis)
    if not validate_release_evidence_bytes("rq7_confirmatory_analysis", analysis_path.read_bytes()).valid:
        raise ValueError("generated RQ7 confirmatory analysis failed its own release validator")

    source_bytes = ANALYSIS_SOURCE_PATH.read_bytes()
    source_validation = validate_release_evidence_bytes("rq7_analysis_source", source_bytes)
    if not source_validation.valid:
        raise ValueError("current H7 analysis source failed release validation: " + "; ".join(source_validation.details))
    provenance = build_rq7_analysis_provenance(analysis, source_bytes=source_bytes)
    provenance_path = output_dir / "rq7-analysis-provenance.json"
    _write_json_atomic(provenance_path, provenance)
    if not validate_release_evidence_bytes("rq7_analysis_provenance", provenance_path.read_bytes()).valid:
        raise ValueError("generated RQ7 analysis provenance failed its release validator")

    environment = payloads["measurement_environment_record"]
    positive_effect: dict[str, Any] | None = None
    positive_effect_reason: str | None = None
    if analysis.get("h7_decision") == "SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE":
        try:
            positive_effect = build_rq7_record_count_effect_evidence(analysis, provenance, environment)
        except ValueError as exc:
            positive_effect_reason = str(exc)
    else:
        positive_effect_reason = "H7-v1 did not produce SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE"

    effect_path = output_dir / "rq7-record-count-effect-evidence.json"
    if positive_effect is not None:
        _write_json_atomic(effect_path, positive_effect)
        effect_validation = validate_release_evidence_bytes("rq7_record_count_effect_evidence", effect_path.read_bytes())
        if not effect_validation.valid:
            raise ValueError("generated positive H7 effect attestation failed release validation: " + "; ".join(effect_validation.details))
    elif effect_path.exists():
        effect_path.unlink()

    artifacts = [
        _artifact(paths["experiment_manifest"], "experiment_manifest"),
        _artifact(paths["machine_profile"], "machine_profile"),
        _artifact(paths["generated_migration_campaign"], "generated_migration_campaign"),
        _artifact(paths["generated_migration_campaign_summary"], "generated_migration_campaign_summary"),
        _artifact(paths["generated_migration_transition_cost_evidence"], "generated_migration_transition_cost_evidence"),
        _artifact(paths["measurement_environment_record"], "measurement_environment_record"),
        _artifact(analysis_path, "rq7_confirmatory_analysis"),
        _artifact(provenance_path, "rq7_analysis_provenance"),
        {
            "role": "rq7_analysis_source",
            "path": str(ANALYSIS_SOURCE_PATH.resolve()),
            "sha256": _sha256_bytes(source_bytes),
        },
    ]
    claims = [
        {
            "type": "generated_migration_transition_cost_measured",
            "text": "Same-process generated-migration transition costs were measured for the complete frozen RQ7 matrix on the packaged machine/toolchain identity.",
            "evidence_roles": [
                "experiment_manifest",
                "generated_migration_campaign",
                "generated_migration_campaign_summary",
                "generated_migration_transition_cost_evidence",
                "machine_profile",
            ],
        }
    ]
    if positive_effect is not None:
        artifacts.append(_artifact(effect_path, "rq7_record_count_effect_evidence"))
        claims.append(
            {
                "type": "rq7_systematic_record_count_effect",
                "text": "H7-v1 supports a systematic record-count effect within the frozen RQ7 single-machine scope represented by this evidence package.",
                "evidence_roles": [
                    "experiment_manifest",
                    "generated_migration_campaign",
                    "generated_migration_transition_cost_evidence",
                    "machine_profile",
                    "measurement_environment_record",
                    "rq7_confirmatory_analysis",
                    "rq7_analysis_provenance",
                    "rq7_analysis_source",
                    "rq7_record_count_effect_evidence",
                ],
            }
        )

    descriptor = {
        "version": version,
        "commit": _measurement_commit(payloads["machine_profile"]),
        "artifacts": artifacts,
        "claims": claims,
    }
    descriptor_path = output_dir / "rq7-release-descriptor.json"
    _write_json_atomic(descriptor_path, descriptor)

    package_dir = output_dir / "evidence-package"
    package = build_evidence_package(descriptor, package_dir, zip_output=zip_output)
    if package["manifest"]["release_state"] != "CLAIMS_EVIDENCE_COMPLETE":
        raise ValueError("RQ7 finalization produced a release package blocked by claim evidence")

    result = {
        "schema": "morpheus-rq7-finalization-report-v1",
        "study_id": analysis["study_id"],
        "measurement_source_commit": descriptor["commit"],
        "campaign_sha256": analysis["campaign_sha256"],
        "analysis_sha256": analysis["analysis_sha256"],
        "analysis_source_sha256": provenance["analysis_source_sha256"],
        "analysis_provenance_sha256": provenance["provenance_sha256"],
        "h7_decision": analysis["h7_decision"],
        "positive_effect_attestation_created": positive_effect is not None,
        "positive_effect_not_created_reason": positive_effect_reason,
        "positive_effect_attestation_sha256": positive_effect.get("attestation_sha256") if positive_effect is not None else None,
        "descriptor_path": str(descriptor_path),
        "analysis_path": str(analysis_path),
        "analysis_provenance_path": str(provenance_path),
        "effect_attestation_path": str(effect_path) if positive_effect is not None else None,
        "package_dir": str(package_dir),
        "package_release_state": package["manifest"]["release_state"],
        "release_manifest_sha256": package["manifest"]["manifest_sha256"],
        "zip_path": str(zip_output.resolve()) if zip_output is not None else None,
        "truth_boundaries": [
            "Finalization performs offline analysis and evidence packaging only; it does not rerun or replace timing measurements.",
            "A negative or unconfirmed H7 result remains packageable as measured transition-cost evidence but cannot mint the positive record-count-effect attestation or claim.",
            "The release manifest commit identifies the measurement source commit from the packaged machine profile; the exact later analysis implementation is independently bound by source-byte provenance.",
        ],
    }
    _write_json_atomic(output_dir / "rq7-finalization-report.json", result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Finalize a complete local MORPHEUS RQ7 run: validate persisted evidence, run H7 offline, bind exact analysis "
            "implementation provenance, conditionally mint the positive-effect attestation, and build a deterministic package."
        )
    )
    parser.add_argument("run_dir", type=Path, help="Directory emitted by scripts/run_generated_migration_campaign.py")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for final analysis, descriptor and evidence package")
    parser.add_argument("--version", required=True, help="Release/evidence version label")
    parser.add_argument("--zip", dest="zip_output", type=Path, default=None, help="Optional deterministic evidence ZIP path")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = finalize_rq7_evidence(
            args.run_dir,
            args.output_dir,
            version=args.version,
            zip_output=args.zip_output,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"rq7 finalization failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
