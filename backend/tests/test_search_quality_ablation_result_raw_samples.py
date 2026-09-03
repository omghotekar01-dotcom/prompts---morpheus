from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_result_artifact_verification import (
    AblationResultArtifactVerificationConsistency,
)
from app.search_quality_ablation_result_raw_samples import (
    EVIDENCE_STATE,
    bind_ablation_result_raw_samples,
)

P45_VERIFICATION = "11" * 32
ARTIFACT_VERIFICATION = "22" * 32
EXECUTION = "33" * 32
COMMIT = "44" * 20
ANALYSIS = "55" * 32
TESTS = "66" * 32
LOCK = "77" * 32
WORKFLOW = "88" * 32
RUNTIME = "python-3.14-linux-x86_64"
RAW = {
    "seed-1337.jsonl": b'{"latency_ns":101}\n{"latency_ns":103}\n',
    "seed-2027.jsonl": b'{"latency_ns":99}\n{"latency_ns":102}\n',
}


def _artifact(
    raw_samples: dict[str, bytes] = RAW,
    *,
    inventory_complete: object = True,
    declared_override: list[dict[str, object]] | None = None,
    automatic_control_allowed: object = False,
) -> bytes:
    declared = declared_override
    if declared is None:
        declared = [
            {"artifact_id": artifact_id, "sha256": hashlib.sha256(content).hexdigest()}
            for artifact_id, content in sorted(raw_samples.items())
        ]
    return json.dumps(
        {
            "schema": "morpheus.ablation-result/v1",
            "raw_sample_evidence": {
                "inventory_complete": inventory_complete,
                "artifacts": declared,
            },
            "automatic_control_allowed": automatic_control_allowed,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _p45(raw: bytes) -> AblationResultArtifactVerificationConsistency:
    return AblationResultArtifactVerificationConsistency(
        provenance_verification_sha256="99" * 32,
        result_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        artifact_verification_sha256=ARTIFACT_VERIFICATION,
        execution_provenance_sha256=EXECUTION,
        implementation_commit_sha=COMMIT,
        analysis_code_sha256=ANALYSIS,
        test_code_sha256=TESTS,
        dependency_lock_sha256=LOCK,
        ci_workflow_sha256=WORKFLOW,
        runtime_id=RUNTIME,
        result_artifact_verification_sha256=P45_VERIFICATION,
        artifact_byte_consistency_verified=True,
    )


def test_p46_binds_exact_raw_sample_bytes_deterministically() -> None:
    raw = _artifact()
    first = bind_ablation_result_raw_samples(_p45(raw), result_artifact=raw, raw_sample_artifacts=RAW)
    second = bind_ablation_result_raw_samples(
        _p45(raw),
        result_artifact=raw.decode(),
        raw_sample_artifacts={key: value.decode() for key, value in reversed(list(RAW.items()))},
    )

    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.raw_sample_bytes_bound is True
    assert first.raw_sample_artifact_count == 2
    assert first.automatic_control_allowed is False
    assert len(first.raw_sample_inventory_sha256) == 64
    assert len(first.raw_sample_binding_sha256) == 64


def test_p46_binding_changes_when_supplied_raw_sample_bytes_change() -> None:
    original_raw = _artifact()
    original = bind_ablation_result_raw_samples(
        _p45(original_raw), result_artifact=original_raw, raw_sample_artifacts=RAW
    )

    changed_samples = dict(RAW)
    changed_samples["seed-1337.jsonl"] = RAW["seed-1337.jsonl"] + b'{"latency_ns":104}\n'
    changed_raw = _artifact(changed_samples)
    changed = bind_ablation_result_raw_samples(
        _p45(changed_raw), result_artifact=changed_raw, raw_sample_artifacts=changed_samples
    )

    assert changed.raw_sample_inventory_sha256 != original.raw_sample_inventory_sha256
    assert changed.raw_sample_binding_sha256 != original.raw_sample_binding_sha256


def test_p46_rejects_raw_sample_sha_drift() -> None:
    declared = [
        {"artifact_id": artifact_id, "sha256": hashlib.sha256(content).hexdigest()}
        for artifact_id, content in sorted(RAW.items())
    ]
    declared[0]["sha256"] = "aa" * 32
    raw = _artifact(declared_override=declared)

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        bind_ablation_result_raw_samples(_p45(raw), result_artifact=raw, raw_sample_artifacts=RAW)


def test_p46_rejects_missing_unknown_and_duplicate_inventory_members() -> None:
    declared = [
        {"artifact_id": "seed-1337.jsonl", "sha256": hashlib.sha256(RAW["seed-1337.jsonl"]).hexdigest()}
    ]
    raw = _artifact(declared_override=declared)
    with pytest.raises(ValueError, match="inventory mismatch"):
        bind_ablation_result_raw_samples(_p45(raw), result_artifact=raw, raw_sample_artifacts=RAW)

    declared.append({"artifact_id": "unknown.jsonl", "sha256": "bb" * 32})
    raw = _artifact(declared_override=declared)
    with pytest.raises(ValueError, match="inventory mismatch"):
        bind_ablation_result_raw_samples(_p45(raw), result_artifact=raw, raw_sample_artifacts=RAW)

    duplicate = [
        {"artifact_id": "seed-1337.jsonl", "sha256": hashlib.sha256(RAW["seed-1337.jsonl"]).hexdigest()},
        {"artifact_id": "seed-1337.jsonl", "sha256": hashlib.sha256(RAW["seed-1337.jsonl"]).hexdigest()},
    ]
    raw = _artifact(declared_override=duplicate)
    with pytest.raises(ValueError, match="duplicate artifact_id"):
        bind_ablation_result_raw_samples(
            _p45(raw), result_artifact=raw, raw_sample_artifacts={"seed-1337.jsonl": RAW["seed-1337.jsonl"]}
        )


def test_p46_rejects_incomplete_or_empty_raw_sample_inventory() -> None:
    raw = _artifact(inventory_complete=False)
    with pytest.raises(ValueError, match="inventory_complete=true"):
        bind_ablation_result_raw_samples(_p45(raw), result_artifact=raw, raw_sample_artifacts=RAW)

    raw = _artifact()
    with pytest.raises(ValueError, match="raw_sample_artifacts cannot be empty"):
        bind_ablation_result_raw_samples(_p45(raw), result_artifact=raw, raw_sample_artifacts={})


def test_p46_rejects_result_byte_drift_and_automatic_control() -> None:
    raw = _artifact()
    with pytest.raises(ValueError, match="result_artifact bytes"):
        bind_ablation_result_raw_samples(_p45(raw), result_artifact=raw + b" ", raw_sample_artifacts=RAW)

    control_raw = _artifact(automatic_control_allowed=True)
    with pytest.raises(ValueError, match="automatic_control_allowed"):
        bind_ablation_result_raw_samples(
            _p45(control_raw), result_artifact=control_raw, raw_sample_artifacts=RAW
        )


def test_p46_rejects_incompatible_incomplete_or_control_authorizing_p45() -> None:
    raw = _artifact()
    with pytest.raises(ValueError, match="incompatible evidence_state"):
        bind_ablation_result_raw_samples(
            replace(_p45(raw), evidence_state="OTHER"), result_artifact=raw, raw_sample_artifacts=RAW
        )
    with pytest.raises(ValueError, match="P45 artifact-byte consistency"):
        bind_ablation_result_raw_samples(
            replace(_p45(raw), artifact_byte_consistency_verified=False),
            result_artifact=raw,
            raw_sample_artifacts=RAW,
        )
    with pytest.raises(ValueError, match="automatic control"):
        bind_ablation_result_raw_samples(
            replace(_p45(raw), automatic_control_allowed=True),
            result_artifact=raw,
            raw_sample_artifacts=RAW,
        )


def test_p46_rejects_duplicate_normalized_supplied_ids_and_empty_bytes() -> None:
    raw = _artifact({"sample": b"x"}, declared_override=[{"artifact_id": "sample", "sha256": hashlib.sha256(b"x").hexdigest()}])
    with pytest.raises(ValueError, match="duplicate normalized artifact_id"):
        bind_ablation_result_raw_samples(
            _p45(raw), result_artifact=raw, raw_sample_artifacts={"sample": b"x", " sample ": b"x"}
        )

    with pytest.raises(ValueError, match="cannot be empty"):
        bind_ablation_result_raw_samples(
            _p45(raw), result_artifact=raw, raw_sample_artifacts={"sample": b""}
        )


def test_p46_normalizes_declared_hash_case_and_outer_whitespace() -> None:
    declared = [
        {
            "artifact_id": "seed-1337.jsonl",
            "sha256": "  " + hashlib.sha256(RAW["seed-1337.jsonl"]).hexdigest().upper() + "  ",
        },
        {
            "artifact_id": "seed-2027.jsonl",
            "sha256": hashlib.sha256(RAW["seed-2027.jsonl"]).hexdigest().upper(),
        },
    ]
    raw = _artifact(declared_override=declared)
    report = bind_ablation_result_raw_samples(
        replace(_p45(raw), result_artifact_verification_sha256="  " + P45_VERIFICATION.upper() + "  "),
        result_artifact=raw,
        raw_sample_artifacts=RAW,
    )
    assert report.result_artifact_verification_sha256 == P45_VERIFICATION
