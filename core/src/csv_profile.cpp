#include "morpheus/csv_profile.hpp"

#include <exception>
#include <iostream>
#include <iterator>
#include <string>

int main() {
    try {
        const std::string text{
            std::istreambuf_iterator<char>(std::cin),
            std::istreambuf_iterator<char>()
        };
        const auto profile = morpheus::csv_profile::profile(text);
        std::cout << "PROFILE_V1 " << profile.record_count << " "
                  << profile.columns.size() << "\n";
        for (const auto& col : profile.columns) {
            std::cout << "FIELD " << col.name << " " << col.type << " "
                      << col.distinct_values << "\n";
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "CSV profiling rejected: " << error.what() << "\n";
        return 2;
    }
}
