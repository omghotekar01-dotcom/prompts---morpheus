from backend.app.evidence_chain import build_evidence_chain, verify_evidence_chain


def test_chain_is_deterministic_and_verified():
    a = "a" * 64
    b = "b" * 64
    left = build_evidence_chain("abcdef1", [b, a])
    right = build_evidence_chain("abcdef1", [a, b])
    assert left == right
    assert verify_evidence_chain(left)
    assert left["production_deployment_authorized"] is False


def test_chain_rejects_tampering_and_boolean_count_alias():
    chain = build_evidence_chain("abcdef1", ["a" * 64])
    tampered = dict(chain)
    tampered["evidence_count"] = True
    assert not verify_evidence_chain(tampered)

    tampered = dict(chain)
    tampered["evidence_digests"] = ["b" * 64]
    assert not verify_evidence_chain(tampered)


def test_chain_rejects_replayed_evidence():
    try:
        build_evidence_chain("abcdef1", ["a" * 64, "a" * 64])
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate evidence must fail closed")
