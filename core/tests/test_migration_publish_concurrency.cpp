#include "morpheus/migration_publish.hpp"

#include <atomic>
#include <cassert>
#include <cstdint>
#include <memory>
#include <string>
#include <thread>
#include <typeindex>
#include <typeinfo>
#include <vector>

namespace {

struct SourceIndex {
    struct Record {
        std::uint64_t id{};
        std::uint64_t value{};
        friend bool operator==(const Record&, const Record&) = default;
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
        friend bool operator==(const Record&, const Record&) = default;
    };

    void insert(const Record& record) { records_.push_back(record); }
    [[nodiscard]] const std::vector<Record>& records() const noexcept { return records_; }

private:
    std::vector<Record> records_;
};

constexpr std::size_t kRecords = 512;

bool source_is_complete(const SourceIndex& index) {
    const auto& rows = index.records();
    return rows.size() == kRecords && !rows.empty() && rows.front().id == 0 &&
           rows.back().id == kRecords - 1 && rows.back().value == (kRecords - 1) * 17U + 5U;
}

bool target_is_complete(const TargetIndex& index) {
    const auto& rows = index.records();
    return rows.size() == kRecords && !rows.empty() && rows.front().id == 0 &&
           rows.back().id == kRecords - 1 && rows.back().value == (kRecords - 1) * 17U + 5U;
}

}  // namespace

int main() {
    auto mutable_source = std::make_shared<SourceIndex>();
    for (std::size_t i = 0; i < kRecords; ++i) {
        mutable_source->insert(SourceIndex::Record{
            static_cast<std::uint64_t>(i),
            static_cast<std::uint64_t>(i * 17U + 5U),
        });
    }
    const std::shared_ptr<const SourceIndex> source = mutable_source;
    assert(source_is_complete(*source));

    morpheus::ErasedVersionedSlot slot("source", source);

    std::atomic<bool> stop{false};
    std::atomic<std::uint64_t> reads{0};
    std::atomic<std::uint64_t> invalid{0};
    std::vector<std::thread> readers;
    readers.reserve(8);

    for (int reader = 0; reader < 8; ++reader) {
        readers.emplace_back([&] {
            while (!stop.load(std::memory_order_relaxed)) {
                const auto version = slot.lease();
                if (!version || !version->payload) {
                    invalid.fetch_add(1, std::memory_order_relaxed);
                    continue;
                }

                if (version->payload_type == std::type_index(typeid(SourceIndex))) {
                    const auto typed = std::shared_ptr<const SourceIndex>(
                        version->payload,
                        static_cast<const SourceIndex*>(version->payload.get())
                    );
                    if (version->candidate_id != "source" || !source_is_complete(*typed)) {
                        invalid.fetch_add(1, std::memory_order_relaxed);
                    }
                } else if (version->payload_type == std::type_index(typeid(TargetIndex))) {
                    const auto typed = std::shared_ptr<const TargetIndex>(
                        version->payload,
                        static_cast<const TargetIndex*>(version->payload.get())
                    );
                    if (version->candidate_id != "target" || !target_is_complete(*typed)) {
                        invalid.fetch_add(1, std::memory_order_relaxed);
                    }
                } else {
                    invalid.fetch_add(1, std::memory_order_relaxed);
                }
                reads.fetch_add(1, std::memory_order_relaxed);
            }
        });
    }

    for (std::size_t transition = 0; transition < 150; ++transition) {
        const auto source_version = slot.lease();
        assert(source_version->candidate_id == "source");
        assert(source_version->payload_type == std::type_index(typeid(SourceIndex)));
        const auto active_source = std::shared_ptr<const SourceIndex>(
            source_version->payload,
            static_cast<const SourceIndex*>(source_version->payload.get())
        );
        assert(active_source.get() == source.get());

        const auto target_generation = morpheus::migrate_validate_and_activate<SourceIndex, TargetIndex>(
            slot,
            source_version,
            "target",
            *active_source,
            [](const SourceIndex::Record& record) {
                return TargetIndex::Record{record.id, record.value};
            },
            [](const TargetIndex& candidate) { return target_is_complete(candidate); }
        );
        assert(target_generation == source_version->generation + 1);

        const auto target_version = slot.lease();
        assert(target_version->candidate_id == "target");
        assert(target_version->payload_type == std::type_index(typeid(TargetIndex)));
        const auto target = std::shared_ptr<const TargetIndex>(
            target_version->payload,
            static_cast<const TargetIndex*>(target_version->payload.get())
        );
        assert(target_is_complete(*target));

        const auto restored_generation = slot.rollback(target_version);
        assert(restored_generation == target_version->generation + 1);
        const auto restored = slot.lease();
        assert(restored->candidate_id == "source");
        assert(restored->payload_type == std::type_index(typeid(SourceIndex)));
        assert(restored->payload.get() == static_cast<const void*>(source.get()));
    }

    stop.store(true, std::memory_order_relaxed);
    for (auto& reader : readers) reader.join();

    assert(reads.load(std::memory_order_relaxed) > 0);
    assert(invalid.load(std::memory_order_relaxed) == 0);
    assert(slot.rollback_depth() == 0);
    return 0;
}
