#include "morpheus/csv_profile.hpp"
#include "morpheus/csv_probe.hpp"

#include <charconv>
#include <exception>
#include <iostream>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>

namespace {
std::size_t parse_size(const char* input) {
    std::string_view text(input);
    std::size_t value{};
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    if (result.ec != std::errc{} || result.ptr != text.data() + text.size()) {
        throw std::invalid_argument("expected non-negative integer argument");
    }
    return value;
}
}

int main(int argc, char** argv) {
    try {
        const std::string text{
            std::istreambuf_iterator<char>(std::cin),
            std::istreambuf_iterator<char>()
        };
        if (argc == 7 && std::string_view(argv[1]) == "--probe") {
            const auto found = morpheus::csv_probe::query(
                text, parse_size(argv[2]), argv[3],
                morpheus::csv_probe::hex_decode(argv[4]),
                morpheus::csv_probe::hex_decode(argv[5]),
                parse_size(argv[6])
            );
            std::cout << "MATCH_V1 " << found.total_rows << " "
                      << found.matched_count << " " << found.field_count
                      << " " << found.preview.size() << "\n";
            for (const auto& row : found.preview) {
                std::cout << "ROW " << row.index;
                for (const auto& value : row.cells) {
                    std::cout << " " << morpheus::csv_probe::hex_encode(value);
                }
                std::cout << "\n";
            }
            return 0;
        }
        if (argc != 1) {
            throw std::invalid_argument("usage: morpheus_csv_profile [--probe col operation lower_hex upper_hex limit]");
        }
        const auto profile = morpheus::csv_profile::profile(text);
        std::cout << "PROFILE_V1 " << profile.record_count << " "
                  << profile.columns.size() << "\n";
        for (const auto& col : profile.columns) {
            std::cout << "FIELD " << col.name << " " << col.type << " "
                      << col.distinct_values << "\n";
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "CSV profiling/query rejected: " << error.what() << "\n";
        return 2;
    }
}
