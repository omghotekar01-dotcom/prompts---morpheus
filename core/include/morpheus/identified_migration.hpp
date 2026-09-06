#pragma once

#include "morpheus/migration.hpp"

#include <cstddef>
#include <istream>
#include <limits>
#include <ostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>

namespace morpheus {

// Identity-bound envelope for portable logical snapshots. This binds the bytes
// to caller-supplied logical schema and record-codec identities before any record
// decoder runs. Identities are exact opaque strings; MORPHEUS does not infer
// semantic compatibility from names, versions or physical candidate types.
inline constexpr std::string_view identified_portable_snapshot_magic =
    "MORPHEUS_IDENTIFIED_LOGICAL_INDEX_SNAPSHOT_V1";

struct IdentifiedPortableSnapshotReadLimits {
    std::size_t max_identity_bytes = 4096;
    std::size_t max_snapshot_bytes = 256U * 1024U * 1024U;
    PortableSnapshotReadLimits snapshot{};
};

inline void validate_portable_snapshot_identity(std::string_view value, std::string_view field_name) {
    if (value.empty()) {
        throw std::invalid_argument("MORPHEUS portable snapshot " + std::string(field_name) + " must not be empty");
    }
}

inline void write_framed_snapshot_field(std::ostream& output, std::string_view value) {
    if (value.size() > static_cast<std::size_t>(std::numeric_limits<std::streamsize>::max())) {
        throw std::runtime_error("MORPHEUS portable snapshot framed field exceeds stream size limits");
    }
    output << value.size() << '\n';
    output.write(value.data(), static_cast<std::streamsize>(value.size()));
    output.put('\n');
    if (!output) throw std::runtime_error("MORPHEUS failed to write portable snapshot framed field");
}

inline std::string read_framed_snapshot_field(
    std::istream& input,
    std::size_t max_bytes,
    std::string_view field_name
) {
    std::string line;
    if (!std::getline(input, line)) {
        throw std::runtime_error("MORPHEUS portable snapshot is missing " + std::string(field_name) + " length");
    }
    const std::size_t size = parse_portable_snapshot_size(line, field_name);
    if (size > max_bytes) {
        throw std::runtime_error("MORPHEUS portable snapshot " + std::string(field_name) + " exceeds limit");
    }
    if (size > static_cast<std::size_t>(std::numeric_limits<std::streamsize>::max())) {
        throw std::runtime_error("MORPHEUS portable snapshot " + std::string(field_name) + " exceeds stream size limits");
    }
    std::string value(size, '\0');
    input.read(value.data(), static_cast<std::streamsize>(size));
    if (static_cast<std::size_t>(input.gcount()) != size) {
        throw std::runtime_error("MORPHEUS portable snapshot " + std::string(field_name) + " is truncated");
    }
    char delimiter = '\0';
    if (!input.get(delimiter) || delimiter != '\n') {
        throw std::runtime_error("MORPHEUS portable snapshot " + std::string(field_name) + " delimiter is invalid");
    }
    return value;
}

template <SnapshotMigratableIndex Index, typename Encoder>
void write_identified_portable_index_snapshot(
    std::ostream& output,
    const Index& source,
    std::string_view schema_identity,
    std::string_view codec_identity,
    Encoder&& encode_record
) {
    validate_portable_snapshot_identity(schema_identity, "schema identity");
    validate_portable_snapshot_identity(codec_identity, "codec identity");

    std::ostringstream inner(std::ios::out | std::ios::binary);
    write_portable_index_snapshot(inner, source, std::forward<Encoder>(encode_record));
    const std::string payload = inner.str();

    output.write(identified_portable_snapshot_magic.data(), static_cast<std::streamsize>(identified_portable_snapshot_magic.size()));
    output.put('\n');
    write_framed_snapshot_field(output, schema_identity);
    write_framed_snapshot_field(output, codec_identity);
    write_framed_snapshot_field(output, payload);
}

template <SnapshotMigratableIndex Index, typename Decoder>
[[nodiscard]] std::shared_ptr<Index> read_identified_portable_index_snapshot(
    std::istream& input,
    std::string_view expected_schema_identity,
    std::string_view expected_codec_identity,
    Decoder&& decode_record,
    IdentifiedPortableSnapshotReadLimits limits = {}
) {
    validate_portable_snapshot_identity(expected_schema_identity, "expected schema identity");
    validate_portable_snapshot_identity(expected_codec_identity, "expected codec identity");
    if (limits.max_identity_bytes == 0 || limits.max_snapshot_bytes == 0) {
        throw std::invalid_argument("MORPHEUS identified portable snapshot limits must be positive");
    }

    std::string line;
    if (!std::getline(input, line) || line != identified_portable_snapshot_magic) {
        throw std::runtime_error("MORPHEUS identified portable snapshot magic mismatch");
    }
    const std::string schema_identity = read_framed_snapshot_field(input, limits.max_identity_bytes, "schema identity");
    const std::string codec_identity = read_framed_snapshot_field(input, limits.max_identity_bytes, "codec identity");
    if (schema_identity != expected_schema_identity) {
        throw std::runtime_error("MORPHEUS portable snapshot schema identity mismatch");
    }
    if (codec_identity != expected_codec_identity) {
        throw std::runtime_error("MORPHEUS portable snapshot codec identity mismatch");
    }

    const std::string payload = read_framed_snapshot_field(input, limits.max_snapshot_bytes, "snapshot payload");
    if (input.peek() != std::char_traits<char>::eof()) {
        throw std::runtime_error("MORPHEUS identified portable snapshot contains trailing bytes");
    }
    std::istringstream inner(payload, std::ios::in | std::ios::binary);
    return read_portable_index_snapshot<Index>(inner, std::forward<Decoder>(decode_record), limits.snapshot);
}

}  // namespace morpheus
