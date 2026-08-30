from types import SimpleNamespace

import pytest

from app.pilot_retry_authorization_registry import register_retry_authorization_consumption


def h(char: str) -> str:
    return char * 64


def auth(**changes):
    data = dict(
        schema="morpheus-pilot-retry-budget-authorization-v1",
        operation="migration-publish",
        key_sha256=h("1"),
        request_sha256=h("2"),
        authorization_sha256=h("3"),
        authorization_sequence=2,
        retry_authorized=True,
    )
    data.update(changes)
    return SimpleNamespace(**data)


def test_consumes_authorization_once_deterministically():
    first = register_retry_authorization_consumption(auth(), consumed_authorization_sha256s=[h("4")])
    second = register_retry_authorization_consumption(auth(), consumed_authorization_sha256s=[h("4")])
    assert first == second
    assert first.authorization_consumed is True
    assert first.consumed_authorization_sha256s == tuple(sorted((h("3"), h("4"))))


def test_reuse_is_rejected():
    with pytest.raises(ValueError, match="already been consumed"):
        register_retry_authorization_consumption(auth(), consumed_authorization_sha256s=[h("3")])


def test_duplicate_registry_evidence_is_rejected():
    with pytest.raises(ValueError, match="duplicates"):
        register_retry_authorization_consumption(auth(), consumed_authorization_sha256s=[h("4"), h("4")])


def test_false_or_truthy_alias_authority_is_rejected():
    with pytest.raises(ValueError, match="explicitly authorize"):
        register_retry_authorization_consumption(auth(retry_authorized=1))


def test_evidence_aliasing_is_rejected():
    with pytest.raises(ValueError, match="independent"):
        register_retry_authorization_consumption(auth(authorization_sha256=h("1")))


def test_boolean_sequence_is_rejected():
    with pytest.raises(ValueError, match="integer"):
        register_retry_authorization_consumption(auth(authorization_sequence=True))
