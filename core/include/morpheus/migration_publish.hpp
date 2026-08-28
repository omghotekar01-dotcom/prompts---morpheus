#pragma once

#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>

#include "morpheus/erased_versioned_slot.hpp"
#include "morpheus/migration.hpp"

namespace morpheus {

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

}  // namespace morpheus
