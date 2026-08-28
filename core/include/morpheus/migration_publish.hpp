#pragma once

#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <typeindex>
#include <typeinfo>
#include <utility>

#include "morpheus/erased_versioned_slot.hpp"
#include "morpheus/migration.hpp"

namespace morpheus {

struct MigrationHealthResult {
    std::uint64_t published_generation{};
    std::uint64_t active_generation{};
    std::string target_candidate_id;
    bool accepted{};
    bool rolled_back{};
    std::string evidence_state;
};

// Rebuild a different target index type from the source index's logical record
// snapshot, validate the shadow candidate, then atomically publish it through a
// generation-bound ErasedVersionedSlot lease.
//
// This is the native bridge between logical state transfer and cross-candidate
// publication. It deliberately migrates logical records rather than copying
// layout-specific pointers/buckets/nodes. The source object remains untouched.
//
// Concurrency truth boundary: the snapshot is point-in-time with respect to the
// caller. If writers can mutate SourceIndex concurrently, the caller must hold
// an application-level snapshot/read barrier while this function captures
// source.records(). This helper does not invent a synchronization policy for
// arbitrary generated indexes.
template <
    SnapshotMigratableIndex SourceIndex,
    SnapshotMigratableIndex TargetIndex,
    typename Converter,
    typename ShadowValidator>
[[nodiscard]] std::uint64_t migrate_validate_and_activate(
    ErasedVersionedSlot& slot,
    const std::shared_ptr<const ErasedVersionedSlot::Version>& expected_version,
    std::string target_candidate_id,
    const SourceIndex& source,
    Converter&& converter,
    ShadowValidator&& shadow_validator
) {
    if (!expected_version) throw std::invalid_argument("expected_version cannot be null");
    if (!expected_version->payload) throw std::invalid_argument("expected_version payload cannot be null");
    if (expected_version->payload_type != std::type_index(typeid(SourceIndex))) {
        throw std::invalid_argument("migration source type does not match expected active version");
    }
    if (expected_version->payload.get() != static_cast<const void*>(std::addressof(source))) {
        throw std::invalid_argument("migration source is not the payload bound to expected active version");
    }

    const auto snapshot = capture_index_snapshot(source);
    const auto expected_record_count = snapshot.size();
    auto target = rebuild_and_validate_foreign_index<TargetIndex>(
        snapshot,
        std::forward<Converter>(converter),
        std::forward<ShadowValidator>(shadow_validator)
    );

    // The reconstruction helper already performed semantic shadow validation.
    // Publication still carries a minimal invariant check so a malformed target
    // cannot be installed if this helper is later refactored independently.
    return slot.activate_validated<TargetIndex>(
        expected_version,
        std::move(target_candidate_id),
        std::shared_ptr<const TargetIndex>(std::move(target)),
        [expected_record_count](const TargetIndex& candidate) {
            return candidate.records().size() == expected_record_count;
        }
    );
}

// Execute the complete local migration transaction: shadow rebuild/validation,
// exact-generation publication, then a post-publication health check against the
// newly active typed payload. A failed health check automatically rolls back by
// exact version lease, so an intervening ABA transition cannot be mistaken for
// the generation that was just published.
//
// The post-publication validator should be bounded and side-effect free. It may
// run semantic probes, invariant checks or local health queries. Returning false
// triggers rollback. Exceptions from the validator also trigger best-effort
// rollback and are then rethrown to preserve the underlying failure signal.
template <
    SnapshotMigratableIndex SourceIndex,
    SnapshotMigratableIndex TargetIndex,
    typename Converter,
    typename ShadowValidator,
    typename PostPublishValidator>
[[nodiscard]] MigrationHealthResult migrate_publish_with_health_gate(
    ErasedVersionedSlot& slot,
    const std::shared_ptr<const ErasedVersionedSlot::Version>& expected_version,
    std::string target_candidate_id,
    const SourceIndex& source,
    Converter&& converter,
    ShadowValidator&& shadow_validator,
    PostPublishValidator&& post_publish_validator
) {
    const std::string target_id_copy = target_candidate_id;
    const auto published_generation = migrate_validate_and_activate<SourceIndex, TargetIndex>(
        slot,
        expected_version,
        std::move(target_candidate_id),
        source,
        std::forward<Converter>(converter),
        std::forward<ShadowValidator>(shadow_validator)
    );

    const auto published = slot.lease();
    if (!published || published->generation != published_generation || published->candidate_id != target_id_copy) {
        throw std::runtime_error("published migration generation changed before post-publication health gate");
    }
    if (published->payload_type != std::type_index(typeid(TargetIndex))) {
        throw std::runtime_error("published migration payload type changed before post-publication health gate");
    }

    const auto target = slot.template lease_as<TargetIndex>();
    bool healthy = false;
    try {
        healthy = static_cast<bool>(std::forward<PostPublishValidator>(post_publish_validator)(*target));
    } catch (...) {
        try {
            (void)slot.rollback(published);
        } catch (...) {
            // Preserve the original health-check exception. Callers can inspect
            // slot state and evidence logs if even the exact-version rollback
            // was concurrently invalidated.
        }
        throw;
    }

    if (!healthy) {
        const auto rollback_generation = slot.rollback(published);
        return MigrationHealthResult{
            published_generation,
            rollback_generation,
            target_id_copy,
            false,
            true,
            "POST_PUBLICATION_HEALTH_REJECTED_ROLLED_BACK",
        };
    }

    return MigrationHealthResult{
        published_generation,
        published_generation,
        target_id_copy,
        true,
        false,
        "SHADOW_VALIDATED_PUBLISHED_AND_HEALTH_ACCEPTED",
    };
}

}  // namespace morpheus
