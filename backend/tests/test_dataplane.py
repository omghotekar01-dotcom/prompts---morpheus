from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.dataplane import VersionedArtifactRouter


A = "a" * 64
B = "b" * 64
V1 = "1" * 64
V2 = "2" * 64


def test_old_reader_lease_survives_atomic_activation_and_new_reader_sees_new_version() -> None:
    router = VersionedArtifactRouter()
    router.bootstrap("service", candidate_id="candidate-a", artifact_sha256=A, verification_manifest_sha256=V1)
    old_lease = router.lease("service")

    router.stage(
        "service",
        candidate_id="candidate-b",
        artifact_sha256=B,
        verification_manifest_sha256=V2,
    )
    activated = router.activate(
        "service",
        expected_from_candidate_id="candidate-a",
        expected_to_candidate_id="candidate-b",
    )
    new_lease = router.lease("service")

    assert old_lease.version.candidate_id == "candidate-a"
    assert old_lease.version.generation == 1
    assert new_lease.version.candidate_id == "candidate-b"
    assert new_lease.version.generation == 2
    assert activated["active"]["candidate_id"] == "candidate-b"
    assert activated["rollback_depth"] == 1


def test_rollback_restores_previous_candidate_with_monotonic_generation() -> None:
    router = VersionedArtifactRouter()
    router.bootstrap("service", candidate_id="candidate-a", artifact_sha256=A, verification_manifest_sha256=V1)
    router.stage("service", candidate_id="candidate-b", artifact_sha256=B, verification_manifest_sha256=V2)
    router.activate(
        "service",
        expected_from_candidate_id="candidate-a",
        expected_to_candidate_id="candidate-b",
    )
    restored = router.rollback("service", reason="post-activation health check failed")

    assert restored["active"]["candidate_id"] == "candidate-a"
    assert restored["active"]["generation"] == 3
    assert restored["rollback_depth"] == 0
    assert restored["history"][-1]["kind"] == "atomic_reference_rollback"


def test_concurrent_leases_never_observe_partial_or_unknown_version() -> None:
    router = VersionedArtifactRouter()
    router.bootstrap("service", candidate_id="candidate-a", artifact_sha256=A, verification_manifest_sha256=V1)

    def sample_many() -> set[tuple[str, int]]:
        return {
            (router.lease("service").version.candidate_id, router.lease("service").version.generation)
            for _ in range(500)
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        before = [executor.submit(sample_many) for _ in range(4)]
        router.stage("service", candidate_id="candidate-b", artifact_sha256=B, verification_manifest_sha256=V2)
        router.activate(
            "service",
            expected_from_candidate_id="candidate-a",
            expected_to_candidate_id="candidate-b",
        )
        after = [executor.submit(sample_many) for _ in range(4)]

    observed = set().union(*(future.result() for future in before + after))
    assert observed <= {("candidate-a", 1), ("candidate-b", 2)}
    assert ("candidate-b", 2) in observed


def test_activation_fails_closed_when_expected_source_or_target_changed() -> None:
    router = VersionedArtifactRouter()
    router.bootstrap("service", candidate_id="candidate-a", artifact_sha256=A, verification_manifest_sha256=V1)
    router.stage("service", candidate_id="candidate-b", artifact_sha256=B, verification_manifest_sha256=V2)

    try:
        router.activate(
            "service",
            expected_from_candidate_id="wrong-source",
            expected_to_candidate_id="candidate-b",
        )
    except ValueError as exc:
        assert "active candidate changed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("source identity mismatch did not block activation")

    assert router.get("service")["active"]["candidate_id"] == "candidate-a"
    assert router.get("service")["staged"]["candidate_id"] == "candidate-b"
