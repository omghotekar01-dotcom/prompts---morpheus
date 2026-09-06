#include "morpheus/identified_migration.hpp"
#include "morpheus/migration.hpp"
#include "morpheus/versioned_slot.hpp"

#include <cassert>
#include <cstdint>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
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

struct AlternateIndex {
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
    static_assert(morpheus::SnapshotMigratableIndex<AlternateIndex>);

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

    // Cross-type reconstruction models two independently generated candidate
    // classes that share logical schema but have different C++ Record types.
    auto alternate = morpheus::rebuild_and_validate_foreign_index<AlternateIndex>(
        snapshot,
        [](const TestIndex::Record& record) {
            return AlternateIndex::Record{record.id, record.value};
        },
        [](const AlternateIndex& candidate) {
            return candidate.records().size() == 3 && candidate.records().front().id == 1;
        }
    );
    assert(alternate->records().size() == snapshot.size());
    for (std::size_t i = 0; i < snapshot.size(); ++i) {
        assert(alternate->records()[i].id == snapshot[i].id);
        assert(alternate->records()[i].value == snapshot[i].value);
    }

    bool foreign_validator_rejected = false;
    try {
        (void)morpheus::rebuild_and_validate_foreign_index<AlternateIndex>(
            snapshot,
            [](const TestIndex::Record& record) {
                return AlternateIndex::Record{record.id, record.value};
            },
            [](const AlternateIndex&) { return false; }
        );
    } catch (const std::runtime_error&) {
        foreign_validator_rejected = true;
    }
    assert(foreign_validator_rejected);

    // Identity-bound process handoff must reject an incompatible schema or
    // codec before the caller's decoder is allowed to interpret record bytes.
    const auto encode_record = [](const TestIndex::Record& record) {
        return std::to_string(record.id) + ":" + std::to_string(record.value);
    };
    int decode_calls = 0;
    const auto decode_record = [&decode_calls](std::string_view payload) {
        ++decode_calls;
        const auto separator = payload.find(':');
        if (separator == std::string_view::npos) throw std::runtime_error("invalid test record");
        return TestIndex::Record{
            std::stoull(std::string(payload.substr(0, separator))),
            std::stoull(std::string(payload.substr(separator + 1))),
        };
    };

    std::ostringstream encoded(std::ios::out | std::ios::binary);
    morpheus::write_identified_portable_index_snapshot(
        encoded,
        *active,
        "test-record-schema-v1",
        "decimal-colon-codec-v1",
        encode_record
    );
    const std::string identified_bytes = encoded.str();

    std::istringstream accepted_input(identified_bytes, std::ios::in | std::ios::binary);
    auto recovered = morpheus::read_identified_portable_index_snapshot<TestIndex>(
        accepted_input,
        "test-record-schema-v1",
        "decimal-colon-codec-v1",
        decode_record
    );
    assert(recovered->records() == active->records());
    assert(decode_calls == 3);

    decode_calls = 0;
    bool schema_mismatch_rejected = false;
    try {
        std::istringstream rejected_input(identified_bytes, std::ios::in | std::ios::binary);
        (void)morpheus::read_identified_portable_index_snapshot<TestIndex>(
            rejected_input,
            "test-record-schema-v2",
            "decimal-colon-codec-v1",
            decode_record
        );
    } catch (const std::runtime_error&) {
        schema_mismatch_rejected = true;
    }
    assert(schema_mismatch_rejected);
    assert(decode_calls == 0);

    decode_calls = 0;
    bool codec_mismatch_rejected = false;
    try {
        std::istringstream rejected_input(identified_bytes, std::ios::in | std::ios::binary);
        (void)morpheus::read_identified_portable_index_snapshot<TestIndex>(
            rejected_input,
            "test-record-schema-v1",
            "decimal-colon-codec-v2",
            decode_record
        );
    } catch (const std::runtime_error&) {
        codec_mismatch_rejected = true;
    }
    assert(codec_mismatch_rejected);
    assert(decode_calls == 0);

    return 0;
}
