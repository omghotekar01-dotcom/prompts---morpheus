#pragma once

// Reference scan over *actual submitted CSV bytes* for honest query-result
// validation. This is NOT an indexed performance benchmark.
#include "morpheus/csv_profile.hpp"

#include <charconv>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace morpheus::csv_probe {

inline std::string hex_encode(const std::string& text) {
    static constexpr char digits[] = "0123456789abcdef";
    if (text.empty()) return "-";
    std::string result;
    result.reserve(text.size() * 2);
    for (unsigned char c : text) {
        result.push_back(digits[c >> 4]);
        result.push_back(digits[c & 15]);
    }
    return result;
}

inline std::string hex_decode(const std::string& value) {
    if (value == "-") return "";
    if (value.size() % 2) throw std::invalid_argument("invalid probe hex length");
    if (value.size() > 8192) throw std::invalid_argument("probe input too large");
    std::string result;
    result.reserve(value.size() / 2);
    auto digit = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
    };
    for (std::size_t i = 0; i < value.size(); i += 2) {
        const int hi = digit(value[i]);
        const int lo = digit(value[i + 1]);
        if (hi < 0 || lo < 0) throw std::invalid_argument("invalid probe hex character");
        result.push_back(static_cast<char>((hi << 4) | lo));
    }
    return result;
}

inline int comparison(const std::string& a, const std::string& b, const std::string& type) {
    if (type == "uint64") {
        std::uint64_t lhs{}, rhs{};
        const auto l = std::from_chars(a.data(), a.data() + a.size(), lhs);
        const auto r = std::from_chars(b.data(), b.data() + b.size(), rhs);
        if (l.ec != std::errc{} || l.ptr != a.data() + a.size() ||
            r.ec != std::errc{} || r.ptr != b.data() + b.size()) {
            throw std::invalid_argument("probe value must be a non-negative integer for this field");
        }
        return (lhs > rhs) - (lhs < rhs);
    }
    if (type == "int") {
        std::int64_t lhs{}, rhs{};
        const auto l = std::from_chars(a.data(), a.data() + a.size(), lhs);
        const auto r = std::from_chars(b.data(), b.data() + b.size(), rhs);
        if (l.ec != std::errc{} || l.ptr != a.data() + a.size() ||
            r.ec != std::errc{} || r.ptr != b.data() + b.size()) {
            throw std::invalid_argument("probe value must be an integer for this field");
        }
        return (lhs > rhs) - (lhs < rhs);
    }
    if (type == "double") {
        if (!csv_profile::finite_number(a) || !csv_profile::finite_number(b)) {
            throw std::invalid_argument("probe value must be numeric for this field");
        }
        const double lhs = std::strtod(a.c_str(), nullptr);
        const double rhs = std::strtod(b.c_str(), nullptr);
        return (lhs > rhs) - (lhs < rhs);
    }
    return a.compare(b) > 0 ? 1 : a.compare(b) < 0 ? -1 : 0;
}

struct MatchedRow {
    std::size_t index; // 1-based data-row index excluding CSV header
    std::vector<std::string> cells;
};

struct Result {
    std::size_t matched_count = 0;
    std::size_t total_rows = 0;
    std::size_t field_count = 0;
    std::vector<MatchedRow> preview;
};

inline Result query(const std::string& csv, std::size_t column,
                    const std::string& kind,
                    const std::string& lower,
                    const std::string& upper,
                    std::size_t limit = 20) {
    if (kind != "point_lookup" && kind != "filter" &&
        kind != "prefix_search" && kind != "range_scan") {
        throw std::invalid_argument("unsupported reference-scan operation");
    }
    if (limit > 50) throw std::invalid_argument("reference scan preview limit exceeds 50");
    const auto profile = csv_profile::profile(csv);
    if (column >= profile.columns.size()) throw std::invalid_argument("unknown CSV field index");
    if (kind == "prefix_search" && profile.columns[column].type != "string") {
        throw std::invalid_argument("prefix search requires a string field");
    }
    const std::string type = profile.columns[column].type;
    if (kind == "range_scan" && comparison(lower, upper, type) > 0) {
        throw std::invalid_argument("range lower bound exceeds upper bound");
    }
    const auto rows = csv_profile::read_rows(csv);
    Result result;
    result.total_rows = profile.record_count;
    result.field_count = profile.columns.size();
    for (std::size_t i = 1; i < rows.size(); ++i) {
        const std::string& val = rows[i][column];
        bool matches = false;
        if (kind == "prefix_search") {
            matches = val.starts_with(lower);
        } else if (kind == "range_scan") {
            matches = comparison(val, lower, type) >= 0 && comparison(val, upper, type) <= 0;
        } else {
            matches = comparison(val, lower, type) == 0;
        }
        if (matches) {
            ++result.matched_count;
            if (result.preview.size() < limit) result.preview.push_back({i, rows[i]});
        }
    }
    return result;
}

} // namespace morpheus::csv_probe
