#include "morpheus/erased_versioned_slot.hpp"
#include "morpheus/migration.hpp"

#include <cassert>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <vector>

struct SourceIndex {
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

struct TargetIndex {
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
    auto source = std::make_shared<SourceIndex>();
    source->insert({1, 10});
    source->insert({2, 20});
    source->insert({3, 30});

    morpheus::ErasedVersionedSlot slot("candidate-source", std::shared_ptr<const SourceIndex>(source));
    const auto observed = slot.lease();
    assert(observed->generation == 1);
    assert(observed->candidate_id == "candidate-source");
    assert(slot.lease_as<SourceIndex>()->records().size() == 3);

    const auto snapshot = morpheus::capture_index_snapshot(*source);
    auto target = morpheus::rebuild_and_validate_foreign_index<TargetIndex>(
        snapshot,
        [](const SourceIndex::Record& record) {
            return TargetIndex::Record{record.id, record.value};
        },
        [](const TargetIndex& candidate) {
            return candidate.records().size() == 3 && candidate.records()[2].value == 30;
        }
    );

    const auto generation_two = slot.activate_validated(
        observed,
        "candidate-target",
        std::shared_ptr<const TargetIndex>(target),
        [](const TargetIndex& candidate) { return candidate.records().size() == 3; }
    );
    assert(generation_two == 2);
    assert(slot.rollback_depth() == 1);
    assert(slot.lease()->candidate_id == "candidate-target");
    assert(slot.lease_as<TargetIndex>()->records()[1].value == 20);

    bool wrong_type_rejected = false;
    try {
        (void)slot.lease_as<SourceIndex>();
    } catch (const std::bad_cast&) {
        wrong_type_rejected = true;
    }
    assert(wrong_type_rejected);

    // The old source lease remains valid even after target publication.
    auto old_source = std::shared_ptr<const SourceIndex>(
        observed->payload,
        static_cast<const SourceIndex*>(observed->payload.get())
    );
    assert(old_source->records().size() == 3);

    const auto target_observed = slot.lease();
    const auto generation_three = slot.rollback(target_observed);
    assert(generation_three == 3);
    assert(slot.lease()->candidate_id == "candidate-source");
    assert(slot.lease_as<SourceIndex>()->records()[0].id == 1);
    assert(slot.rollback_depth() == 0);

    // Stale-version/ABA defense: an observed version cannot publish after the
    // slot has advanced even if the same candidate identity returns later.
    const auto stale = slot.lease();
    auto target_two = std::make_shared<TargetIndex>(*target);
    assert(slot.activate_validated(
        stale,
        "candidate-target",
        std::shared_ptr<const TargetIndex>(target_two),
        [](const TargetIndex&) { return true; }
    ) == 4);
    const auto target_generation_four = slot.lease();
    assert(slot.rollback(target_generation_four) == 5);

    bool stale_publication_rejected = false;
    try {
        (void)slot.activate_validated(
            stale,
            "candidate-target-2",
            std::shared_ptr<const TargetIndex>(target_two),
            [](const TargetIndex&) { return true; }
        );
    } catch (const std::runtime_error&) {
        stale_publication_rejected = true;
    }
    assert(stale_publication_rejected);
    assert(slot.lease()->candidate_id == "candidate-source");
    assert(slot.lease()->generation == 5);

    // Rollback is also generation-aware. Re-enter candidate-target so an old
    // lease has the same candidate identity but an obsolete generation.
    const auto source_generation_five = slot.lease();
    assert(slot.activate_validated(
        source_generation_five,
        "candidate-target",
        std::shared_ptr<const TargetIndex>(target_two),
        [](const TargetIndex&) { return true; }
    ) == 6);

    bool stale_rollback_rejected = false;
    try {
        (void)slot.rollback(target_generation_four);
    } catch (const std::runtime_error&) {
        stale_rollback_rejected = true;
    }
    assert(stale_rollback_rejected);
    assert(slot.lease()->candidate_id == "candidate-target");
    assert(slot.lease()->generation == 6);
    assert(slot.rollback_depth() == 1);

    const auto target_generation_six = slot.lease();
    assert(slot.rollback(target_generation_six) == 7);
    assert(slot.lease()->candidate_id == "candidate-source");
    assert(slot.rollback_depth() == 0);

    return 0;
}
