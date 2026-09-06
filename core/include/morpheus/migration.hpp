#pragma once

#include <algorithm>
#include <charconv>
#include <concepts>
#include <cstddef>
#include <istream>
#include <limits>
#include <memory>
#include <ostream>
#include <stdexcept>
#include <string>
#include <string_view>
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

template <SnapshotMigratableIndex TargetIndex, typename SourceRecord, typename Converter>
[[nodiscard]] std::shared_ptr<TargetIndex> rebuild_index_from_foreign_snapshot(
    const std::vector<SourceRecord>& snapshot,
    Converter&& converter
) {
    auto target = std::make_shared<TargetIndex>();
    auto&& convert = converter;
    for (const auto& record : snapshot) target->insert(convert(record));
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

template <SnapshotMigratableIndex TargetIndex, typename SourceRecord, typename Converter, typename Validator>
[[nodiscard]] std::shared_ptr<TargetIndex> rebuild_and_validate_foreign_index(
    const std::vector<SourceRecord>& snapshot,
    Converter&& converter,
    Validator&& validator
) {
    auto candidate = rebuild_index_from_foreign_snapshot<TargetIndex>(snapshot, converter);
    if (candidate->records().size() != snapshot.size()) {
        throw std::runtime_error("MORPHEUS foreign shadow reconstruction changed logical record count");
    }
    if (!std::forward<Validator>(validator)(*candidate)) {
        throw std::runtime_error("MORPHEUS foreign shadow reconstruction failed candidate validation");
    }
    return candidate;
}

// Portable logical-state framing for process-boundary reconstruction.
//
// The caller owns the Record codec because generated Record schemas vary. MORPHEUS
// supplies deterministic length framing, strict parsing, resource limits and fresh
// index reconstruction. Callers should open file streams in binary mode when byte-
// identical snapshots are required across platforms.
//
// This is logical record transfer, not native memory serialization. It does not
// preserve pointers, allocator state, reader leases, staged routing state or live
// concurrent mutations, and it is not crash-consistent or distributed persistence.
inline constexpr std::string_view portable_index_snapshot_magic =
    "MORPHEUS_LOGICAL_INDEX_SNAPSHOT_V1";

struct PortableSnapshotReadLimits {
    std::size_t max_records = 1'000'000;
    std::size_t max_record_bytes = 16U * 1024U * 1024U;
    std::size_t max_total_record_bytes = 256U * 1024U * 1024U;
};

[[nodiscard]] inline std::size_t parse_portable_snapshot_size(
    std::string_view text,
    std::string_view field_name
) {
    if (text.empty()) {
        throw std::runtime_error("MORPHEUS portable snapshot " + std::string(field_name) + " is empty");
    }
    std::size_t value = 0;
    const char* begin = text.data();
    const char* end = begin + text.size();
    const auto result = std::from_chars(begin, end, value);
    if (result.ec != std::errc{} || result.ptr != end) {
        throw std::runtime_error("MORPHEUS portable snapshot " + std::string(field_name) + " is invalid");
    }
    return value;
}

template <SnapshotMigratableIndex Index, typename Encoder>
void write_portable_index_snapshot(
    std::ostream& output,
    const Index& source,
    Encoder&& encode_record
) {
    const auto snapshot = capture_index_snapshot(source);
    output.write(portable_index_snapshot_magic.data(), static_cast<std::streamsize>(portable_index_snapshot_magic.size()));
    output.put('\n');
    output << snapshot.size() << '\n';
    if (!output) throw std::runtime_error("MORPHEUS failed to write portable snapshot header");

    auto&& encode = encode_record;
    for (const auto& record : snapshot) {
        std::string payload = encode(record);
        if (payload.size() > static_cast<std::size_t>(std::numeric_limits<std::streamsize>::max())) {
            throw std::runtime_error("MORPHEUS encoded record exceeds stream size limits");
        }
        output << payload.size() << '\n';
        output.write(payload.data(), static_cast<std::streamsize>(payload.size()));
        output.put('\n');
        if (!output) throw std::runtime_error("MORPHEUS failed to write portable snapshot record");
    }
}

template <SnapshotMigratableIndex Index, typename Decoder>
[[nodiscard]] std::shared_ptr<Index> read_portable_index_snapshot(
    std::istream& input,
    Decoder&& decode_record,
    PortableSnapshotReadLimits limits = {}
) {
    if (limits.max_records == 0 || limits.max_record_bytes == 0 || limits.max_total_record_bytes == 0) {
        throw std::invalid_argument("MORPHEUS portable snapshot limits must be positive");
    }

    std::string line;
    if (!std::getline(input, line) || line != portable_index_snapshot_magic) {
        throw std::runtime_error("MORPHEUS portable snapshot magic mismatch");
    }
    if (!std::getline(input, line)) {
        throw std::runtime_error("MORPHEUS portable snapshot is missing record count");
    }
    const std::size_t record_count = parse_portable_snapshot_size(line, "record count");
    if (record_count > limits.max_records) {
        throw std::runtime_error("MORPHEUS portable snapshot exceeds record-count limit");
    }

    IndexSnapshot<Index> snapshot;
    snapshot.reserve(record_count);
    std::size_t total_payload_bytes = 0;
    auto&& decode = decode_record;

    for (std::size_t index = 0; index < record_count; ++index) {
        if (!std::getline(input, line)) {
            throw std::runtime_error("MORPHEUS portable snapshot is missing record length");
        }
        const std::size_t payload_size = parse_portable_snapshot_size(line, "record length");
        if (payload_size > limits.max_record_bytes) {
            throw std::runtime_error("MORPHEUS portable snapshot record exceeds per-record limit");
        }
        if (total_payload_bytes > limits.max_total_record_bytes
            || payload_size > limits.max_total_record_bytes - total_payload_bytes) {
            throw std::runtime_error("MORPHEUS portable snapshot exceeds total payload limit");
        }
        if (payload_size > static_cast<std::size_t>(std::numeric_limits<std::streamsize>::max())) {
            throw std::runtime_error("MORPHEUS portable snapshot record exceeds stream size limits");
        }

        std::string payload(payload_size, '\0');
        input.read(payload.data(), static_cast<std::streamsize>(payload_size));
        if (static_cast<std::size_t>(input.gcount()) != payload_size) {
            throw std::runtime_error("MORPHEUS portable snapshot record is truncated");
        }
        char delimiter = '\0';
        if (!input.get(delimiter) || delimiter != '\n') {
            throw std::runtime_error("MORPHEUS portable snapshot record delimiter is invalid");
        }

        snapshot.push_back(decode(std::string_view(payload)));
        total_payload_bytes += payload_size;
    }

    if (input.peek() != std::char_traits<char>::eof()) {
        throw std::runtime_error("MORPHEUS portable snapshot contains trailing bytes");
    }
    return rebuild_index_from_snapshot<Index>(snapshot);
}

}  // namespace morpheus
