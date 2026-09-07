from __future__ import annotations

import hashlib

from app.process_transfer_fencing import create_fenced_process_transfer_restart_authentication_tag


KEY = hashlib.sha256(b"fenced-restart-identity-binding-key-material").digest()
HEAD_SHA256 = hashlib.sha256(b"fenced-restart-identity-binding-head").hexdigest()


def _tag(*, key_id: str = "receiver-key-v1", fencing_authority_id: str = "receiver-fencing-service-a") -> str:
    return create_fenced_process_transfer_restart_authentication_tag(
        authentication_key=KEY,
        key_id=key_id,
        authority_id="receiver-a",
        sequence=1,
        head_sha256=HEAD_SHA256,
        fencing_authority_id=fencing_authority_id,
        previous_fencing_counter=11,
        fencing_counter=12,
    )


def test_fencing_authentication_tag_binds_key_and_fencing_authority_identities() -> None:
    baseline = _tag()

    assert baseline == _tag()
    assert baseline != _tag(key_id="receiver-key-v2")
    assert baseline != _tag(fencing_authority_id="receiver-fencing-service-b")
