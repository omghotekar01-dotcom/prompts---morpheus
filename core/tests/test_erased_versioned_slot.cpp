#include "morpheus/erased_versioned_slot.hpp"
#include "morpheus/migration.hpp"

#include <cassert>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <vector>

struct SourceIndex {
    struct Record { std::uint64_t id{}; std::uint64_t value{}; bool operator==(const Record&) const = default; };
    void insert(const Record& record) { records_.push_back(record); }
    [[nodiscard]] const std::vector<Record>& records() const noexcept { return records_; }
private: std::vector<Record> records_;
};
struct TargetIndex {
    struct Record { std::uint64_t id{}; std::uint64_t value{}; bool operator==(const Record&) const = default; };
    void insert(const Record& record) { records_.push_back(record); }
    [[nodiscard]] const std::vector<Record>& records() const noexcept { return records_; }
private: std::vector<Record> records_;
};

int main() {
    auto source = std::make_shared<SourceIndex>();
    source->insert({1, 10}); source->insert({2, 20}); source->insert({3, 30});
    morpheus::ErasedVersionedSlot slot("candidate-source", std::shared_ptr<const SourceIndex>(source));
    const auto observed = slot.lease();
    assert(observed->generation == 1);
    assert(slot.lease_as<SourceIndex>()->records().size() == 3);

    const auto snapshot = morpheus::capture_index_snapshot(*source);
    auto target = morpheus::rebuild_and_validate_foreign_index<TargetIndex>(snapshot,
        [](const SourceIndex::Record& r) { return TargetIndex::Record{r.id, r.value}; },
        [](const TargetIndex& c) { return c.records().size() == 3 && c.records()[2].value == 30; });
    assert(slot.activate_validated(observed, "candidate-target", std::shared_ptr<const TargetIndex>(target),
        [](const TargetIndex& c) { return c.records().size() == 3; }) == 2);
    assert(slot.rollback_depth() == 1);

    const auto target_observed = slot.lease();
    assert(slot.rollback(target_observed) == 3);
    assert(slot.rollback_depth() == 0);

    const auto stale = slot.lease();
    auto target_two = std::make_shared<TargetIndex>(*target);
    assert(slot.activate_validated(stale, "candidate-target", std::shared_ptr<const TargetIndex>(target_two),
        [](const TargetIndex&) { return true; }) == 4);
    const auto target_generation_four = slot.lease();
    assert(slot.rollback(target_generation_four) == 5);

    bool stale_publication_rejected = false;
    try { (void)slot.activate_validated(stale, "candidate-target-2", std::shared_ptr<const TargetIndex>(target_two),
        [](const TargetIndex&) { return true; }); } catch (const std::runtime_error&) { stale_publication_rejected = true; }
    assert(stale_publication_rejected);

    const auto source_generation_five = slot.lease();
    assert(slot.activate_validated(source_generation_five, "candidate-target", std::shared_ptr<const TargetIndex>(target_two),
        [](const TargetIndex&) { return true; }) == 6);
    bool stale_rollback_rejected = false;
    try { (void)slot.rollback(target_generation_four); } catch (const std::runtime_error&) { stale_rollback_rejected = true; }
    assert(stale_rollback_rejected);
    assert(slot.rollback_depth() == 1);

    // Stabilization is version-bound and releases historical payloads only for
    // the exact active generation observed by the coordinator.
    bool stale_retirement_rejected = false;
    try { (void)slot.retire_rollback_history(target_generation_four); }
    catch (const std::runtime_error&) { stale_retirement_rejected = true; }
    assert(stale_retirement_rejected);
    assert(slot.rollback_depth() == 1);

    const auto stable_target = slot.lease();
    assert(slot.retire_rollback_history(stable_target) == 1);
    assert(slot.rollback_depth() == 0);
    assert(slot.retire_rollback_history(stable_target) == 0);

    bool rollback_after_retirement_rejected = false;
    try { (void)slot.rollback(stable_target); }
    catch (const std::runtime_error&) { rollback_after_retirement_rejected = true; }
    assert(rollback_after_retirement_rejected);
    assert(slot.lease()->candidate_id == "candidate-target");
    assert(slot.lease()->generation == 6);
    return 0;
}
