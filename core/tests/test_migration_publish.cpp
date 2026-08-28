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
    auto mutable_source = std::make_shared<SourceIndex>();
    mutable_source->insert({1, "alpha"});
    mutable_source->insert({2, "beta"});
    mutable_source->insert({3, "gamma"});
    const std::shared_ptr<const SourceIndex> source = mutable_source;

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

    // Failed semantic shadow validation must not publish or deepen rollback history.
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

    // A target can pass shadow correctness but still fail post-publication
    // application health. The transaction must automatically restore the exact
    // source generation payload while keeping generation monotonic.
    const auto health_rejected = morpheus::migrate_publish_with_health_gate<SourceIndex, TargetIndex>(
        slot,
        slot.lease(),
        "target-health-reject",
        *slot.lease_as<SourceIndex>(),
        convert_record,
        [](const TargetIndex& candidate) { return candidate.records().size() == 3; },
        [](const TargetIndex&) { return false; }
    );
    assert(health_rejected.published_generation == 4);
    assert(health_rejected.active_generation == 5);
    assert(!health_rejected.accepted);
    assert(health_rejected.rolled_back);
    assert(health_rejected.evidence_state == "POST_PUBLICATION_HEALTH_REJECTED_ROLLED_BACK");
    assert(slot.lease()->candidate_id == "source-index");
    assert(slot.lease()->generation == 5);
    assert(slot.lease_as<SourceIndex>().get() == source.get());

    // A healthy target remains active and keeps one rollback generation until a
    // higher-level stabilization policy retires it.
    const auto source_after_health_rollback = slot.lease();
    const auto health_accepted = morpheus::migrate_publish_with_health_gate<SourceIndex, TargetIndex>(
        slot,
        source_after_health_rollback,
        "target-health-accepted",
        *slot.lease_as<SourceIndex>(),
        convert_record,
        [](const TargetIndex& candidate) { return candidate.records().size() == 3; },
        [](const TargetIndex& candidate) {
            return candidate.records()[1].key == 2 && candidate.records()[1].value == "beta";
        }
    );
    assert(health_accepted.published_generation == 6);
    assert(health_accepted.active_generation == 6);
    assert(health_accepted.accepted);
    assert(!health_accepted.rolled_back);
    assert(health_accepted.evidence_state == "SHADOW_VALIDATED_PUBLISHED_AND_HEALTH_ACCEPTED");
    assert(slot.lease()->candidate_id == "target-health-accepted");
    assert(slot.rollback_depth() == 1);

    const auto final_target_version = slot.lease();
    assert(slot.rollback(final_target_version) == 7);
    assert(slot.lease()->candidate_id == "source-index");
    assert(slot.lease_as<SourceIndex>().get() == source.get());
    return 0;
}