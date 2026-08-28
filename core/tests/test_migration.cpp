#include "morpheus/migration.hpp"
#include "morpheus/versioned_slot.hpp"

#include <cassert>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <vector>

struct TestIndex {
    struct Record {
        std::uint64_t id{};
        std::uint64_t value{};
        bool operator==(const Record&) const = default;
    };

    void insert(const Record& record) { records_.push_back(record); }
    [[nodiscard]] const std::vector<Record>& records() const noexcept { return records_; }

private:
    std::vector<Record> records_;
};

int main() {
    static_assert(morpheus::SnapshotMigratableIndex<TestIndex>);

    auto active = std::make_shared<TestIndex>();
    active->insert({1, 10});
    active->insert({2, 20});
    active->insert({3, 30});

    const auto snapshot = morpheus::capture_index_snapshot(*active);
    assert(snapshot.size() == 3);

    auto shadow = morpheus::rebuild_and_validate_index<TestIndex>(snapshot, [](const TestIndex& candidate) {
        return candidate.records().size() == 3 && candidate.records()[1].value == 20;
    });
    assert(morpheus::snapshot_matches_index(snapshot, *shadow));
    assert(shadow.get() != active.get());

    using Slot = morpheus::VersionedSlot<TestIndex>;
    Slot slot("candidate-a", std::const_pointer_cast<const TestIndex>(active));
    const auto generation = slot.activate_validated(
        "candidate-a",
        "candidate-b",
        std::const_pointer_cast<const TestIndex>(shadow),
        [&](const TestIndex& current, const TestIndex& staged) {
            return current.records() == snapshot && staged.records() == snapshot;
        }
    );
    assert(generation == 2);
    assert(slot.lease()->candidate_id == "candidate-b");
    assert(slot.lease()->payload->records() == snapshot);

    const auto rollback_generation = slot.rollback("candidate-b");
    assert(rollback_generation == 3);
    assert(slot.lease()->candidate_id == "candidate-a");
    assert(slot.lease()->payload->records() == snapshot);

    bool validator_rejected = false;
    try {
        (void)morpheus::rebuild_and_validate_index<TestIndex>(snapshot, [](const TestIndex&) { return false; });
    } catch (const std::runtime_error&) {
        validator_rejected = true;
    }
    assert(validator_rejected);

    return 0;
}
