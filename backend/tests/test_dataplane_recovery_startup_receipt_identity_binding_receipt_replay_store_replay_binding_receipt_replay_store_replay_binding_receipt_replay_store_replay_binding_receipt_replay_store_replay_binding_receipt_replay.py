from __future__ import annotations

import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P95_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P97_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P98_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt import (
    SCHEMA as P99_SCHEMA,
    canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    replay_recovery_startup_replayed_receipt_retained_identity_binding_receipt,
)

FIELDS = (
    ("sequence", "int"),
    ("lineage_sha256", "sha"),
    ("binding_receipt_payload_sha256", "sha"),
    ("binding_receipt_payload_size_bytes", "int"),
    ("receipt_identity_binding_sha256", "sha"),
    ("retained_identity_payload_sha256", "sha"),
    ("retained_identity_payload_size_bytes", "int"),
    ("replay_stored_identity_binding_sha256", "sha"),
    ("replay_binding_receipt_payload_sha256", "sha"),
    ("replay_binding_receipt_payload_size_bytes", "int"),
    ("retained_replay_identity_payload_sha256", "sha"),
    ("retained_replay_identity_payload_size_bytes", "int"),
    ("replay_retained_identity_binding_sha256", "sha"),
    ("replay_retained_identity_binding_receipt_payload_sha256", "sha"),
    ("replay_retained_identity_binding_receipt_payload_size_bytes", "int"),
    ("retained_replay_receipt_identity_payload_sha256", "sha"),
    ("retained_replay_receipt_identity_payload_size_bytes", "int"),
    ("replay_retained_receipt_identity_binding_sha256", "sha"),
    ("replay_retained_receipt_identity_binding_receipt_payload_sha256", "sha"),
    ("replay_retained_receipt_identity_binding_receipt_payload_size_bytes", "int"),
    ("retained_replayed_receipt_identity_payload_sha256", "sha"),
    ("retained_replayed_receipt_identity_payload_size_bytes", "int"),
    ("replayed_receipt_retained_identity_binding_sha256", "sha"),
)


def canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def p98_values() -> dict[str, object]:
    values: dict[str, object] = {}
    sha_index = 0
    size_value = 101
    for field, kind in FIELDS:
        if field == "replayed_receipt_retained_identity_binding_sha256":
            continue
        if kind == "sha":
            sha_index += 1
            values[field] = hashlib.sha256(f"p100-{sha_index}".encode()).hexdigest()
        else:
            values[field] = 17 if field == "sequence" else size_value
            size_value += 1

    values["replayed_receipt_retained_identity_binding_sha256"] = canonical_sha(
        {
            **values,
            "p95_evidence_state": P95_EVIDENCE_STATE,
            "p97_evidence_state": P97_EVIDENCE_STATE,
        }
    )
    return values


def p98_evidence() -> RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence:
    return RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence(
        **p98_values(),
        p95_contract_verified=True,
        p97_contract_verified=True,
        cross_evidence_identity_verified=True,
    )


def receipt():
    return canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(p98_evidence())


def replay(payload: bytes | None = None, *, sha: str | None = None, size: int | None = None):
    encoded = receipt()
    raw = encoded.payload if payload is None else payload
    return replay_recovery_startup_replayed_receipt_retained_identity_binding_receipt(
        raw,
        expected_payload_sha256=encoded.payload_sha256 if payload is None and sha is None else (
            hashlib.sha256(raw).hexdigest() if sha is None else sha
        ),
        expected_payload_size_bytes=encoded.payload_size_bytes if payload is None and size is None else (
            len(raw) if size is None else size
        ),
    )


def recanonicalize(document: object) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def test_p100_replays_real_p98_to_p99_receipt_deterministically():
    first = replay()
    second = replay()
    encoded = receipt()
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.p98_evidence_state == P98_EVIDENCE_STATE
    assert first.replayed_receipt_retained_identity_binding_receipt_payload_sha256 == encoded.payload_sha256
    assert first.replayed_receipt_retained_identity_binding_receipt_payload_size_bytes == encoded.payload_size_bytes
    assert first.expected_payload_identity_verified is True
    assert first.canonical_receipt_verified is True
    assert first.dependency_state_verified is True
    assert first.replayed_receipt_retained_identity_binding_recomputed_verified is True
    assert first.automatic_control_allowed is False


@pytest.mark.parametrize("bad_sha,bad_size", [("f" * 64, None), (None, 1)])
def test_p100_rejects_wrong_expected_outer_identity(bad_sha, bad_size):
    encoded = receipt()
    with pytest.raises(ValueError, match="mismatch"):
        replay(
            encoded.payload,
            sha=bad_sha or encoded.payload_sha256,
            size=bad_size or encoded.payload_size_bytes,
        )


def test_p100_rejects_noncanonical_json_even_when_outer_identity_matches():
    document = json.loads(receipt().payload)
    raw = json.dumps(document, sort_keys=False, indent=2).encode("utf-8")
    with pytest.raises(ValueError, match="strict canonical JSON"):
        replay(raw)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda d: d.__setitem__("schema", "morpheus.recovery.p99.forged.v1"), "schema identifier"),
        (lambda d: d.__setitem__("p98_evidence_state", "forged"), "P98 evidence state"),
        (lambda d: d.__setitem__("extra", 1), "schema is incompatible"),
    ],
)
def test_p100_rejects_schema_and_dependency_state_drift(mutation, match):
    document = json.loads(receipt().payload)
    mutation(document)
    with pytest.raises(ValueError, match=match):
        replay(recanonicalize(document))


@pytest.mark.parametrize("value", [True, 0, -1])
def test_p100_rejects_invalid_sequence(value):
    document = json.loads(receipt().payload)
    document["sequence"] = value
    with pytest.raises(ValueError, match="positive integer"):
        replay(recanonicalize(document))


def test_p100_rejects_malformed_semantic_sha():
    document = json.loads(receipt().payload)
    document["lineage_sha256"] = "Z" * 64
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        replay(recanonicalize(document))


def test_p100_rejects_forged_serialized_p98_binding_with_recomputed_outer_identity():
    document = json.loads(receipt().payload)
    document["replayed_receipt_retained_identity_binding_sha256"] = hashlib.sha256(b"forged-binding").hexdigest()
    with pytest.raises(ValueError, match="binding recomputation mismatch"):
        replay(recanonicalize(document))


@pytest.mark.parametrize(
    "field",
    [field for field, _ in FIELDS if field != "replayed_receipt_retained_identity_binding_sha256"],
)
def test_p100_rejects_semantic_tampering_with_fresh_outer_identity(field):
    document = json.loads(receipt().payload)
    kind = dict(FIELDS)[field]
    document[field] = (
        9999
        if kind == "int"
        else hashlib.sha256(f"tampered-{field}".encode()).hexdigest()
    )
    with pytest.raises(ValueError, match="binding recomputation mismatch"):
        replay(recanonicalize(document))


@pytest.mark.parametrize(
    "raw,match",
    [
        (b"\xff", "not valid UTF-8"),
        (b"{", "not valid JSON"),
        (b"[]", "JSON object"),
    ],
)
def test_p100_rejects_invalid_payload_encodings_and_shapes(raw, match):
    with pytest.raises(ValueError, match=match):
        replay(raw)


@pytest.mark.parametrize("payload", [None, "not-bytes", bytearray(b"x")])
def test_p100_rejects_incompatible_payload_type(payload):
    with pytest.raises(ValueError, match="must be bytes"):
        replay_recovery_startup_replayed_receipt_retained_identity_binding_receipt(
            payload,
            expected_payload_sha256="0" * 64,
            expected_payload_size_bytes=1,
        )


def test_p100_truth_boundary_remains_read_only_and_non_claiming():
    result = replay()
    boundary = result.as_dict()["truth_boundary"].lower()
    for phrase in (
        "does not authenticate",
        "freshness",
        "rollback",
        "authorize startup or mutation",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
        "automatic-control authority",
    ):
        assert phrase in boundary
    assert P99_SCHEMA.startswith("morpheus.recovery.p99.")
    assert result.automatic_control_allowed is False
    assert "read-only" in TRUTH_BOUNDARY.lower()
