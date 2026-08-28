#pragma once

#include <concepts>
#include <memory>
#include <stdexcept>
#include <utility>
#include <vector>

namespace morpheus {

// Minimal type-safe state-transfer protocol for generated record-backed indexes.
//
// The source index exports its logical live-record sequence through records(). A
// fresh target index is reconstructed by replaying insert(record), allowing the
// target to build a completely different physical layout while the source stays
// untouched. This deliberately transfers logical state, not implementation
// internals such as node pointers, bucket arrays or allocator state.
template <typename Index>
concept SnapshotMigratableIndex = requires(Index index, const Index const_index, const typename Index::Record& record) {
    typename Index::Record;
    { const_index.records() };
    { index.insert(record) } -> std::same_as<void>;
};

template <SnapshotMigratableIndex Index>
using IndexSnapshot = std::vector<typename Index::Record>;

template <SnapshotMigratableIndex Index>
[[nodiscard]] IndexSnapshot<Index> capture_index_snapshot(const Index& source) {
    const auto& records = source.records();
    return IndexSnapshot<Index>(records.begin(), records.end());
}

template <SnapshotMigratableIndex Index>
[[nodiscard]] std::shared_ptr<Index> rebuild_index_from_snapshot(const IndexSnapshot<Index>& snapshot) {
    auto target = std::make_shared<Index>();
    for (const auto& record : snapshot) target->insert(record);
    return target;
}

template <SnapshotMigratableIndex Index>
[[nodiscard]] bool snapshot_matches_index(const IndexSnapshot<Index>& snapshot, const Index& candidate) {
    const auto& records = candidate.records();
    return records.size() == snapshot.size() && std::equal(records.begin(), records.end(), snapshot.begin());
}

template <SnapshotMigratableIndex Index, typename Validator>
[[nodiscard]] std::shared_ptr<Index> rebuild_and_validate_index(
    const IndexSnapshot<Index>& snapshot,
    Validator&& validator
) {
    auto candidate = rebuild_index_from_snapshot<Index>(snapshot);
    if (!snapshot_matches_index(snapshot, *candidate)) {
        throw std::runtime_error("MORPHEUS shadow reconstruction changed the logical record snapshot");
    }
    if (!std::forward<Validator>(validator)(*candidate)) {
        throw std::runtime_error("MORPHEUS shadow reconstruction failed candidate validation");
    }
    return candidate;
}

}  // namespace morpheus
