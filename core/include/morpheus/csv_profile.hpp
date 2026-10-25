#pragma once

// Exact bounded CSV inspection in C++20; outputs typed, real-data statistics.
// The query workload is deliberately NOT guessed from file contents.

#include <charconv>
#include <cstdint>
#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

namespace morpheus::csv_profile {

struct Column {
    std::string name;
    std::string type; // uint64, int, double, string
    std::size_t distinct_values;
};

struct Result {
    std::size_t record_count;
    std::vector<Column> columns;
};

inline bool valid_identifier(const std::string& input) {
    if (input.empty() || input.size() > 128) return false;
    auto letter = [](char c) {
        return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_';
    };
    if (!letter(input[0])) return false;
    for (char c : input) {
        if (!letter(c) && (c < '0' || c > '9')) return false;
    }
    return true;
}

inline std::vector<std::vector<std::string>> read_rows(const std::string& text) {
    if (text.size() > 1000000) {
        throw std::invalid_argument("CSV exceeds the 1,000,000-byte inspection limit");
    }
    std::vector<std::vector<std::string>> rows;
    std::vector<std::string> row;
    std::string field;
    bool quoted = false;
    bool closed_quote = false;
    auto finish_field = [&] {
        row.push_back(std::move(field));
        field.clear();
        closed_quote = false;
    };
    auto finish_row = [&] {
        finish_field();
        if (rows.empty() && row.size() > 64) {
            throw std::invalid_argument("CSV has more than 64 columns");
        }
        rows.push_back(std::move(row));
        row.clear();
        if (rows.size() > 100001) {
            throw std::invalid_argument("CSV exceeds 100,000 records");
        }
    };
    for (std::size_t i = 0; i < text.size(); ++i) {
        char c = text[i];
        if (quoted) {
            if (c == '"') {
                if (i + 1 < text.size() && text[i + 1] == '"') {
                    field.push_back('"');
                    ++i;
                } else {
                    quoted = false;
                    closed_quote = true;
                }
            } else {
                field.push_back(c);
            }
            continue;
        }
        if (c == '\r') {
            if (i + 1 < text.size() && text[i + 1] == '\n') ++i;
            c = '\n';
        }
        if (c == '\n') {
            finish_row();
        } else if (c == ',') {
            finish_field();
        } else if (c == '"') {
            if (!field.empty() || closed_quote) {
                throw std::invalid_argument("quote must start a CSV field");
            }
            quoted = true;
        } else {
            if (closed_quote) {
                throw std::invalid_argument("unexpected character after closing quote");
            }
            field.push_back(c);
        }
    }
    if (quoted) throw std::invalid_argument("unterminated quoted CSV field");
    if (!row.empty() || !field.empty() || closed_quote) finish_row();
    if (rows.size() < 2) throw std::invalid_argument("CSV needs a header and at least one record");
    return rows;
}

inline bool signed_integer(const std::string& text) {
    if (text.empty()) return false;
    std::int64_t number = 0;
    const auto result = std::from_chars(text.data(), text.data() + text.size(), number);
    return result.ec == std::errc{} && result.ptr == text.data() + text.size();
}

inline bool unsigned_integer(const std::string& text) {
    if (text.empty()) return false;
    std::uint64_t number = 0;
    const auto result = std::from_chars(text.data(), text.data() + text.size(), number);
    return result.ec == std::errc{} && result.ptr == text.data() + text.size();
}

inline bool finite_number(const std::string& text) {
    if (text.empty()) return false;
    char* end = nullptr;
    const double number = std::strtod(text.c_str(), &end);
    return end == text.c_str() + text.size() && std::isfinite(number);
}

inline Result profile(const std::string& text) {
    const auto rows = read_rows(text);
    const auto& headers = rows.front();
    if (headers.empty() || headers.size() > 64) {
        throw std::invalid_argument("CSV must have 1-64 headers");
    }
    std::unordered_set<std::string> names;
    for (const auto& name : headers) {
        if (!valid_identifier(name) || !names.insert(name).second) {
            throw std::invalid_argument("CSV headers must be unique MWS field identifiers");
        }
    }
    for (std::size_t row = 1; row < rows.size(); ++row) {
        if (rows[row].size() != headers.size()) {
            throw std::invalid_argument("CSV row has a different column count from the header");
        }
    }
    Result result;
    result.record_count = rows.size() - 1;
    result.columns.reserve(headers.size());
    for (std::size_t col = 0; col < headers.size(); ++col) {
        std::unordered_set<std::string> distinct;
        bool all_integer = true;
        bool all_numeric = true;
        bool negative = false;
        for (std::size_t row = 1; row < rows.size(); ++row) {
            const auto& value = rows[row][col];
            distinct.insert(value);
            const bool integer = signed_integer(value) || unsigned_integer(value);
            if (!integer) all_integer = false;
            if (!integer && !finite_number(value)) all_numeric = false;
            if (!value.empty() && value[0] == '-') negative = true;
        }
        std::string type = "string";
        if (all_integer) type = negative ? "int" : "uint64";
        else if (all_numeric) type = "double";
        result.columns.push_back({headers[col], type, distinct.size()});
    }
    return result;
}

} // namespace morpheus::csv_profile
