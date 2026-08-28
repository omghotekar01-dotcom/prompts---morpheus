#include "morpheus/migration_publish.hpp"

#include <cassert>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

struct SourceIndex {
    struct Record {
        int key{};
        std::string value;
        friend bool operator==(const Record&, const Record&) = default;
    };

    void insert(const Record& record) { rows.push_back(record); }
    [[nodiscard]] const std::vector<Record>& records() const noexcept { return rows; }

    std::vector<Record> rows;
};

struct TargetIndex {
    struct Record {
        std::int64_t key{};
        std::string value;
        friend bool operator==(const Record&, const Record&) = default;
    };

    void insert(const Record& record) { rows.push_back(record); }
    [[nodiscard]] const std::vector<Record>& records() const noexcept { return rows; }

    std::vector<Record> rows;
};

TargetIndex::Record convert_record(const SourceIndex::Record& source) {
    return TargetIndex::Record{static_cast<std::int64_t>(source.key), source.value};
}

}  // namespace

int main() {
    auto source = std::make_shared<SourceIndex>();
    source->insert({1, "alpha"});
    source->insert({2, "beta"});
    source->insert({3, "gamma"});

    morpheus::ErasedVersionedSlot slot("source-index", source);
    const auto source_version = slot.lease();

    const auto generation = morpheus::migrate_validate_and_activate<SourceIndex, TargetIndex>(
        slot,
        source_version,
        "target-index",
        *source,
        convert_record,
        [](const TargetIndex& candidate) {
            return candidate.records().size() == 3 &&
                   candidate.records()[0].key == 1 &&
                   candidate.records()[2].value == "gamma";
        }
    );

    assert(generation == 2);
    const auto target_version = slot.lease();
    assert(target_version->candidate_id == "target-index");
    assert(target_version->generation == 2);
    const auto target = slot.lease_as<TargetIndex>();
    assert(target->records().size() == 3);
    assert(target->records()[1] == TargetIndex::Record(2, "beta"));

    // Source logical state is copied into a distinct target object and remains
    // unchanged after publication.
    assert(source->records().size() == 3);
    assert(source->records()[0] == SourceIndex::Record(1, "alpha"));

    // The generation-bound publication lease closes a stale shadow-publication
    // window even if a caller still holds the old source Version.
    bool stale_rejected = false;
    try {
        static_cast<void>(morpheus::migrate_validate_and_activate<SourceIndex, TargetIndex>(
            slot,
            source_version,
            "another-target",
            *source,
            convert_record,
            [](const TargetIndex&) { return true; }
        ));
    } catch (const std::runtime_error&) {
        stale_rejected = true;
    }
    assert(stale_rejected);

    // Version-aware rollback restores the exact prior payload type and logical
    // state while advancing generation monotonically.
    const auto rollback_generation = slot.rollback(target_version);
    assert(rollback_generation == 3);
    assert(slot.lease()->candidate_id == "source-index");
    const auto restored = slot.lease_as<SourceIndex>();
    assert(restored->records() == source->records());

    // Failed semantic validation must not publish or deepen rollback history.
    const auto restored_version = slot.lease();
    const auto rollback_depth_before = slot.rollback_depth();
    bool validation_rejected = false;
    try {
        static_cast<void>(morpheus::migrate_validate_and_activate<SourceIndex, TargetIndex>(
            slot,
            restored_version,
            "invalid-target",
            *restored,
            convert_record,
            [](const TargetIndex&) { return false; }
        ));
    } catch (const std::runtime_error&) {
        validation_rejected = true;
    }
    assert(validation_rejected);
    assert(slot.lease()->candidate_id == "source-index");
    assert(slot.lease()->generation == 3);
    assert(slot.rollback_depth() == rollback_depth_before);

    return 0;
}
