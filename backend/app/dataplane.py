from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any


def _validate_sha256(value: str, name: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{name} must be a 64-character hexadecimal digest")
    return normalized


@dataclass(frozen=True)
class ArtifactVersion:
    generation: int
    candidate_id: str
    artifact_sha256: str
    verification_manifest_sha256: str | None
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "candidate_id": self.candidate_id,
            "artifact_sha256": self.artifact_sha256,
            "verification_manifest_sha256": self.verification_manifest_sha256,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ReadLease:
    """Immutable reader snapshot.

    Python object references keep the selected version alive after an atomic
    registry swap, giving old readers snapshot semantics while new readers see
    the newly active version. This is a local in-process routing mechanism, not
    a cross-process/native C++ object migration claim.
    """

    deployment_id: str
    version: ArtifactVersion

    def as_dict(self) -> dict[str, Any]:
        return {"deployment_id": self.deployment_id, "version": self.version.as_dict()}


@dataclass
class _Deployment:
    deployment_id: str
    active: ArtifactVersion
    staged: ArtifactVersion | None = None
    rollback_stack: list[ArtifactVersion] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)


class VersionedArtifactRouter:
    """Thread-safe local artifact router with shadow stage, atomic activation and rollback.

    The critical swap is a single active-reference replacement under an RLock.
    Readers obtain immutable leases and never observe a partially updated
    version. The implementation proves a useful local RCU-style routing
    mechanism, but does not claim that generated native data structures have
    been migrated across processes or that concurrent records were transformed.
    """

    def __init__(self) -> None:
        self._deployments: dict[str, _Deployment] = {}
        self._lock = RLock()

    def bootstrap(
        self,
        deployment_id: str,
        *,
        candidate_id: str,
        artifact_sha256: str,
        verification_manifest_sha256: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not deployment_id or len(deployment_id) > 128:
            raise ValueError("deployment_id must contain 1-128 characters")
        if not candidate_id or len(candidate_id) > 128:
            raise ValueError("candidate_id must contain 1-128 characters")
        artifact = _validate_sha256(artifact_sha256, "artifact_sha256")
        verification = (
            _validate_sha256(verification_manifest_sha256, "verification_manifest_sha256")
            if verification_manifest_sha256 is not None
            else None
        )
        with self._lock:
            if deployment_id in self._deployments:
                raise ValueError(f"deployment already exists: {deployment_id}")
            version = ArtifactVersion(
                generation=1,
                candidate_id=candidate_id,
                artifact_sha256=artifact,
                verification_manifest_sha256=verification,
                metadata=dict(metadata or {}),
            )
            deployment = _Deployment(deployment_id=deployment_id, active=version)
            deployment.history.append(
                {
                    "kind": "bootstrap",
                    "generation": version.generation,
                    "candidate_id": candidate_id,
                    "artifact_sha256": artifact,
                }
            )
            self._deployments[deployment_id] = deployment
            return self._view(deployment)

    def stage(
        self,
        deployment_id: str,
        *,
        candidate_id: str,
        artifact_sha256: str,
        verification_manifest_sha256: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        artifact = _validate_sha256(artifact_sha256, "artifact_sha256")
        verification = _validate_sha256(verification_manifest_sha256, "verification_manifest_sha256")
        if not candidate_id or len(candidate_id) > 128:
            raise ValueError("candidate_id must contain 1-128 characters")
        with self._lock:
            deployment = self._require(deployment_id)
            if candidate_id == deployment.active.candidate_id:
                raise ValueError("staged candidate must differ from active candidate")
            if deployment.staged is not None:
                raise ValueError("deployment already has a staged version")
            version = ArtifactVersion(
                generation=deployment.active.generation + 1,
                candidate_id=candidate_id,
                artifact_sha256=artifact,
                verification_manifest_sha256=verification,
                metadata=dict(metadata or {}),
            )
            deployment.staged = version
            deployment.history.append(
                {
                    "kind": "shadow_staged",
                    "generation": version.generation,
                    "candidate_id": candidate_id,
                    "artifact_sha256": artifact,
                    "verification_manifest_sha256": verification,
                }
            )
            return self._view(deployment)

    def activate(
        self,
        deployment_id: str,
        *,
        expected_from_candidate_id: str,
        expected_to_candidate_id: str,
    ) -> dict[str, Any]:
        with self._lock:
            deployment = self._require(deployment_id)
            if deployment.active.candidate_id != expected_from_candidate_id:
                raise ValueError("active candidate changed before data-plane activation")
            if deployment.staged is None:
                raise ValueError("deployment has no staged version")
            if deployment.staged.candidate_id != expected_to_candidate_id:
                raise ValueError("staged candidate does not match expected migration target")
            previous = deployment.active
            replacement = deployment.staged
            deployment.rollback_stack.append(previous)
            deployment.active = replacement
            deployment.staged = None
            deployment.history.append(
                {
                    "kind": "atomic_reference_activated",
                    "from_candidate_id": previous.candidate_id,
                    "to_candidate_id": replacement.candidate_id,
                    "generation": replacement.generation,
                    "evidence_state": "LOCAL_IN_PROCESS_VERSIONED_REFERENCE_SWAP",
                }
            )
            return self._view(deployment)

    def abort_staged(self, deployment_id: str, *, reason: str) -> dict[str, Any]:
        if not reason:
            raise ValueError("abort reason is required")
        with self._lock:
            deployment = self._require(deployment_id)
            if deployment.staged is None:
                raise ValueError("deployment has no staged version")
            candidate_id = deployment.staged.candidate_id
            deployment.staged = None
            deployment.history.append({"kind": "shadow_aborted", "candidate_id": candidate_id, "reason": reason})
            return self._view(deployment)

    def rollback(self, deployment_id: str, *, reason: str) -> dict[str, Any]:
        if not reason:
            raise ValueError("rollback reason is required")
        with self._lock:
            deployment = self._require(deployment_id)
            if not deployment.rollback_stack:
                raise ValueError("deployment has no committed version to roll back")
            current = deployment.active
            previous = deployment.rollback_stack.pop()
            # A rollback is itself a new generation so version ordering remains
            # monotonic even when candidate identity moves backward.
            restored = ArtifactVersion(
                generation=current.generation + 1,
                candidate_id=previous.candidate_id,
                artifact_sha256=previous.artifact_sha256,
                verification_manifest_sha256=previous.verification_manifest_sha256,
                metadata=dict(previous.metadata),
            )
            deployment.active = restored
            deployment.staged = None
            deployment.history.append(
                {
                    "kind": "atomic_reference_rollback",
                    "from_candidate_id": current.candidate_id,
                    "to_candidate_id": restored.candidate_id,
                    "generation": restored.generation,
                    "reason": reason,
                    "evidence_state": "LOCAL_IN_PROCESS_VERSIONED_REFERENCE_ROLLBACK",
                }
            )
            return self._view(deployment)

    def lease(self, deployment_id: str) -> ReadLease:
        with self._lock:
            deployment = self._require(deployment_id)
            return ReadLease(deployment_id=deployment_id, version=deployment.active)

    def get(self, deployment_id: str) -> dict[str, Any]:
        with self._lock:
            return self._view(self._require(deployment_id))

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._view(self._deployments[key]) for key in sorted(self._deployments)]

    def reset(self) -> None:
        with self._lock:
            self._deployments.clear()

    def _require(self, deployment_id: str) -> _Deployment:
        try:
            return self._deployments[deployment_id]
        except KeyError as exc:
            raise KeyError(f"unknown deployment: {deployment_id}") from exc

    @staticmethod
    def _view(deployment: _Deployment) -> dict[str, Any]:
        return {
            "deployment_id": deployment.deployment_id,
            "active": deployment.active.as_dict(),
            "staged": deployment.staged.as_dict() if deployment.staged else None,
            "rollback_depth": len(deployment.rollback_stack),
            "history": list(deployment.history),
            "evidence_state": "LOCAL_IN_PROCESS_VERSIONED_ARTIFACT_ROUTER",
            "truth_boundary": (
                "Atomic local routing is implemented; native generated-object migration, cross-process swap and record transformation are not implied."
            ),
        }


DATA_PLANE = VersionedArtifactRouter()
