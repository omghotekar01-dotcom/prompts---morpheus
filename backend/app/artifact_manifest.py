from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .artifact_codegen import GeneratedArtifact
from .configuration_ir import lower_and_hash_configuration_ir
from .models import CandidateResult, WorkloadSpec
from .primitive_manifest import primitive_manifest_hash
from .workload_ir import lower_and_hash_workload_ir


ARTIFACT_MANIFEST_VERSION = "morpheus-generated-artifact-manifest-v2"
CODEGEN_VERSION = "morpheus-cpp20-codegen-v3"


@dataclass(frozen=True)
class ArtifactProvenanceManifest:
    schema: str
    codegen_version: str
    candidate_id: str
    namespace_name: str
    header_name: str
    source_sha256: str
    workload_ir_hash: str
    configuration_ir_hash: str
    primitive_manifest_hash: str
    evidence_state: str = "GENERATED_PROVENANCE_BOUND_NOT_COMPILE_VERIFIED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "codegen_version": self.codegen_version,
            "candidate_id": self.candidate_id,
            "namespace_name": self.namespace_name,
            "header_name": self.header_name,
            "source_sha256": self.source_sha256,
            "workload_ir_hash": self.workload_ir_hash,
            "configuration_ir_hash": self.configuration_ir_hash,
            "primitive_manifest_hash": self.primitive_manifest_hash,
            "evidence_state": self.evidence_state,
            "truth_boundary": (
                "This manifest binds generated source bytes to semantic/compiler inputs and implementation-bound primitive identities. "
                "Compilation, behavioral correctness and performance require separate evidence gates."
            ),
        }


def build_artifact_provenance_manifest(
    spec: WorkloadSpec,
    candidate: CandidateResult,
    artifact: GeneratedArtifact,
) -> ArtifactProvenanceManifest:
    if artifact.candidate_id != candidate.id:
        raise ValueError("artifact candidate_id does not match candidate used for provenance")
    _workload_ir, workload_digest = lower_and_hash_workload_ir(spec)
    _configuration_ir, configuration_digest = lower_and_hash_configuration_ir(spec, candidate)
    source_digest = hashlib.sha256(artifact.header_source.encode("utf-8")).hexdigest()
    return ArtifactProvenanceManifest(
        schema=ARTIFACT_MANIFEST_VERSION,
        codegen_version=CODEGEN_VERSION,
        candidate_id=candidate.id,
        namespace_name=artifact.namespace_name,
        header_name=artifact.header_name,
        source_sha256=source_digest,
        workload_ir_hash=workload_digest,
        configuration_ir_hash=configuration_digest,
        primitive_manifest_hash=primitive_manifest_hash(),
    )


def canonical_artifact_manifest_json(manifest: ArtifactProvenanceManifest) -> str:
    return json.dumps(manifest.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def artifact_manifest_hash(manifest: ArtifactProvenanceManifest) -> str:
    return hashlib.sha256(canonical_artifact_manifest_json(manifest).encode("utf-8")).hexdigest()
