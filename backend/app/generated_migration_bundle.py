from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .artifact_codegen import GeneratedArtifact, generate_verified_header
from .artifact_manifest import ArtifactProvenanceManifest, build_artifact_provenance_manifest
from .models import CandidateResult, SynthesisResult, WorkloadSpec


GENERATED_MIGRATION_BUNDLE_SCHEMA = "morpheus-generated-migration-bundle-v1"


@dataclass(frozen=True)
class GeneratedMigrationBundle:
    schema: str
    source_candidate_id: str
    target_candidate_id: str
    source_artifact: GeneratedArtifact
    target_artifact: GeneratedArtifact
    source_manifest: ArtifactProvenanceManifest
    target_manifest: ArtifactProvenanceManifest
    harness_source: str
    harness_sha256: str
    record_count: int
    evidence_state: str = "GENERATED_MIGRATION_BUNDLE_NOT_COMPILE_VERIFIED"

    def as_dict(self, *, include_sources: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "source_candidate_id": self.source_candidate_id,
            "target_candidate_id": self.target_candidate_id,
            "source_manifest": self.source_manifest.as_dict(),
            "target_manifest": self.target_manifest.as_dict(),
            "harness_sha256": self.harness_sha256,
            "record_count": self.record_count,
            "evidence_state": self.evidence_state,
            "truth_boundary": (
                "The bundle deterministically binds two distinct generated physical designs to a native same-process "
                "logical-state migration, shadow-validation, publication, concurrent-reader, health-gate and rollback harness. "
                "Until that harness is compiled and executed by a declared toolchain, this is generated verification input, "
                "not runtime or performance evidence. Cross-process/distributed hot replacement is outside this bundle."
            ),
        }
        if include_sources:
            payload["source_header_name"] = self.source_artifact.header_name
            payload["target_header_name"] = self.target_artifact.header_name
            payload["source_header_source"] = self.source_artifact.header_source
            payload["target_header_source"] = self.target_artifact.header_source
            payload["harness_source"] = self.harness_source
        return payload


def select_distinct_migration_pair(synthesis: SynthesisResult) -> tuple[CandidateResult, CandidateResult]:
    """Return the winner and the best distinct feasible physical candidate.

    Candidate ids are derived from route assignments, so a different id means a
    different synthesized configuration identity. This helper does not claim the
    second candidate is better; it only selects a deterministic migration target.
    """

    source = synthesis.winner
    if source is None:
        raise ValueError("synthesis has no feasible winner to use as migration source")
    for candidate in synthesis.candidates:
        if candidate.feasible and candidate.id != source.id:
            return source, candidate
    raise ValueError("synthesis does not contain two distinct feasible candidates")


def _record_assignment_lines(spec: WorkloadSpec) -> str:
    lines: list[str] = []
    for offset, field in enumerate(spec.fields, start=1):
        kind = field.type.lower()
        if kind in {"string", "str", "text", "char"}:
            expression = f'std::string("{field.name}_") + std::to_string(i)'
        elif kind == "bool":
            expression = f"((i + {offset}) % 2) == 0"
        elif kind in {"float", "double"}:
            expression = f"static_cast<decltype(record.{field.name})>(i + {offset}) + 0.5"
        else:
            # The code generator maps known integral aliases to integer C++
            # types. Unknown user field types currently fall back to std::string.
            if kind not in {
                "uint64",
                "uint64_t",
                "uint32",
                "uint32_t",
                "int",
                "integer",
            }:
                expression = f'std::string("{field.name}_") + std::to_string(i)'
            else:
                expression = f"static_cast<decltype(record.{field.name})>(i + {offset})"
        lines.append(f"        record.{field.name} = {expression};")
    return "\n".join(lines)


def _target_record_expression(spec: WorkloadSpec, source_expression: str) -> str:
    values = ", ".join(f"{source_expression}.{field.name}" for field in spec.fields)
    return f"Target::Record{{{values}}}"


def _build_harness_source(
    spec: WorkloadSpec,
    source_artifact: GeneratedArtifact,
    target_artifact: GeneratedArtifact,
    *,
    record_count: int,
) -> str:
    record_assignments = _record_assignment_lines(spec)
    converted_record = _target_record_expression(spec, "record")
    converted_row = _target_record_expression(spec, "source_rows[i]")

    template = r'''#include "__SOURCE_HEADER__"
#include "__TARGET_HEADER__"
#include "morpheus/migration_publish.hpp"

#include <atomic>
#include <cassert>
#include <chrono>
#include <cstddef>
#include <iostream>
#include <memory>
#include <string>
#include <thread>
#include <typeindex>
#include <typeinfo>
#include <vector>

using Source = __SOURCE_NAMESPACE__::GeneratedIndex;
using Target = __TARGET_NAMESPACE__::GeneratedIndex;
using Version = morpheus::ErasedVersionedSlot::Version;

static_assert(morpheus::SnapshotMigratableIndex<Source>);
static_assert(morpheus::SnapshotMigratableIndex<Target>);

template <typename Payload>
std::shared_ptr<const Payload> payload_as(const std::shared_ptr<const Version>& version) {
    if (!version || version->payload_type != std::type_index(typeid(Payload))) return {};
    return std::shared_ptr<const Payload>(
        version->payload,
        static_cast<const Payload*>(version->payload.get())
    );
}

Target::Record convert_record(const Source::Record& record) {
    return __CONVERTED_RECORD__;
}

bool same_logical_state(const Source& source, const Target& target) {
    const auto& source_rows = source.records();
    const auto& target_rows = target.records();
    if (source_rows.size() != target_rows.size()) return false;
    for (std::size_t i = 0; i < source_rows.size(); ++i) {
        const auto converted = __CONVERTED_ROW__;
        if (!(target_rows[i] == converted)) return false;
    }
    return true;
}

int main() {
    constexpr std::size_t record_count = __RECORD_COUNT__;
    auto mutable_source = std::make_shared<Source>();
    for (std::size_t i = 0; i < record_count; ++i) {
        Source::Record record{};
__RECORD_ASSIGNMENTS__
        mutable_source->insert(record);
    }

    // Materialize the mutable record cache before the object becomes an
    // immutable publication payload. Published versions are then read-only.
    assert(mutable_source->records().size() == record_count);
    const std::shared_ptr<const Source> source = mutable_source;

    morpheus::ErasedVersionedSlot slot("__SOURCE_CANDIDATE__", source);
    const auto initial_version = slot.lease();
    assert(initial_version->candidate_id == "__SOURCE_CANDIDATE__");

    std::atomic<bool> stop{false};
    std::atomic<std::uint64_t> source_reads{0};
    std::atomic<std::uint64_t> target_reads{0};
    std::atomic<std::uint64_t> invalid_reads{0};

    auto reader = [&]() {
        while (!stop.load(std::memory_order_acquire)) {
            const auto version = slot.lease();
            if (!version) {
                ++invalid_reads;
                continue;
            }
            if (version->payload_type == std::type_index(typeid(Source))) {
                const auto typed = payload_as<Source>(version);
                if (!typed || version->candidate_id != "__SOURCE_CANDIDATE__" ||
                    typed->size() != record_count || typed->records().size() != record_count ||
                    std::string(typed->candidate_id()) != "__SOURCE_CANDIDATE__") {
                    ++invalid_reads;
                } else {
                    ++source_reads;
                }
            } else if (version->payload_type == std::type_index(typeid(Target))) {
                const auto typed = payload_as<Target>(version);
                if (!typed || version->candidate_id != "__TARGET_CANDIDATE__" ||
                    typed->size() != record_count || typed->records().size() != record_count ||
                    std::string(typed->candidate_id()) != "__TARGET_CANDIDATE__") {
                    ++invalid_reads;
                } else {
                    ++target_reads;
                }
            } else {
                ++invalid_reads;
            }
        }
    };

    std::vector<std::thread> readers;
    for (int i = 0; i < 4; ++i) readers.emplace_back(reader);

    const auto accepted = morpheus::migrate_publish_with_health_gate<Source, Target>(
        slot,
        initial_version,
        "__TARGET_CANDIDATE__",
        *source,
        convert_record,
        [&](const Target& candidate) {
            // This also materializes the target record cache before publication.
            return same_logical_state(*source, candidate);
        },
        [&](const Target& candidate) {
            return same_logical_state(*source, candidate);
        }
    );
    assert(accepted.accepted);
    assert(!accepted.rolled_back);
    assert(accepted.evidence_state == "SHADOW_VALIDATED_PUBLISHED_AND_HEALTH_ACCEPTED");

    for (int spin = 0; spin < 5000 && target_reads.load(std::memory_order_acquire) < 100; ++spin) {
        std::this_thread::sleep_for(std::chrono::microseconds(50));
    }
    assert(target_reads.load(std::memory_order_acquire) > 0);

    const auto target_version = slot.lease();
    assert(target_version->candidate_id == "__TARGET_CANDIDATE__");
    const auto rollback_generation = slot.rollback(target_version);
    assert(rollback_generation > accepted.published_generation);
    assert(slot.lease()->candidate_id == "__SOURCE_CANDIDATE__");

    // Prove that a candidate which passes shadow correctness but fails the
    // application health gate is restored automatically to the exact source
    // payload family without exposing a malformed reader state.
    const auto rejected = morpheus::migrate_publish_with_health_gate<Source, Target>(
        slot,
        slot.lease(),
        "__TARGET_CANDIDATE__",
        *slot.lease_as<Source>(),
        convert_record,
        [&](const Target& candidate) {
            return same_logical_state(*source, candidate);
        },
        [](const Target&) { return false; }
    );
    assert(!rejected.accepted);
    assert(rejected.rolled_back);
    assert(rejected.evidence_state == "POST_PUBLICATION_HEALTH_REJECTED_ROLLED_BACK");
    assert(slot.lease()->candidate_id == "__SOURCE_CANDIDATE__");

    for (int spin = 0; spin < 1000 && source_reads.load(std::memory_order_acquire) < 100; ++spin) {
        std::this_thread::sleep_for(std::chrono::microseconds(50));
    }

    stop.store(true, std::memory_order_release);
    for (auto& thread : readers) thread.join();

    assert(source_reads.load() > 0);
    assert(target_reads.load() > 0);
    assert(invalid_reads.load() == 0);
    assert(slot.lease_as<Source>().get() == source.get());

    std::cout
        << "MORPHEUS_GENERATED_MIGRATION_OK"
        << " source_reads=" << source_reads.load()
        << " target_reads=" << target_reads.load()
        << " invalid_reads=" << invalid_reads.load()
        << " final_generation=" << slot.lease()->generation
        << "\n";
    return 0;
}
'''

    replacements = {
        "__SOURCE_HEADER__": source_artifact.header_name,
        "__TARGET_HEADER__": target_artifact.header_name,
        "__SOURCE_NAMESPACE__": source_artifact.namespace_name,
        "__TARGET_NAMESPACE__": target_artifact.namespace_name,
        "__SOURCE_CANDIDATE__": source_artifact.candidate_id,
        "__TARGET_CANDIDATE__": target_artifact.candidate_id,
        "__CONVERTED_RECORD__": converted_record,
        "__CONVERTED_ROW__": converted_row,
        "__RECORD_COUNT__": str(record_count),
        "__RECORD_ASSIGNMENTS__": record_assignments,
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template


def build_generated_migration_bundle(
    spec: WorkloadSpec,
    source_candidate: CandidateResult,
    target_candidate: CandidateResult,
    *,
    record_count: int = 128,
) -> GeneratedMigrationBundle:
    if source_candidate.id == target_candidate.id:
        raise ValueError("source and target candidates must be distinct")
    if not source_candidate.feasible or not target_candidate.feasible:
        raise ValueError("source and target candidates must both be feasible")
    if record_count < 1 or record_count > 4096:
        raise ValueError("record_count must be between 1 and 4096")

    source_artifact = generate_verified_header(
        spec,
        source_candidate,
        namespace_name=f"morpheus_source_{source_candidate.id}",
    )
    target_artifact = generate_verified_header(
        spec,
        target_candidate,
        namespace_name=f"morpheus_target_{target_candidate.id}",
    )
    source_manifest = build_artifact_provenance_manifest(spec, source_candidate, source_artifact)
    target_manifest = build_artifact_provenance_manifest(spec, target_candidate, target_artifact)
    if source_manifest.workload_ir_hash != target_manifest.workload_ir_hash:
        raise ValueError("migration candidates are not bound to the same workload IR")
    if source_manifest.configuration_ir_hash == target_manifest.configuration_ir_hash:
        raise ValueError("migration candidates must have distinct configuration IR identities")

    harness_source = _build_harness_source(
        spec,
        source_artifact,
        target_artifact,
        record_count=record_count,
    )
    harness_sha256 = hashlib.sha256(harness_source.encode("utf-8")).hexdigest()
    return GeneratedMigrationBundle(
        schema=GENERATED_MIGRATION_BUNDLE_SCHEMA,
        source_candidate_id=source_candidate.id,
        target_candidate_id=target_candidate.id,
        source_artifact=source_artifact,
        target_artifact=target_artifact,
        source_manifest=source_manifest,
        target_manifest=target_manifest,
        harness_source=harness_source,
        harness_sha256=harness_sha256,
        record_count=record_count,
    )
