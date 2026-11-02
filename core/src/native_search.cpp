#include "morpheus/native_search.hpp"

#include <cstddef>
#include <exception>
#include <iostream>
#include <string>

// Deliberately small, versioned, non-shell protocol. Python is only the API
// transport: all combinatorial search decisions happen in compiled C++20.
// Input must come from a validated WorkloadSpec, never an arbitrary command.
int main() {
    using namespace morpheus::native_search;
    try {
        std::string magic;
        std::string requested_strategy;
        Request request;
        std::size_t query_count = 0;
        if (!(std::cin >> magic) || magic != "MORPHEUS_NATIVE_SEARCH_V1" ||
            !(std::cin >> requested_strategy >> request.max_candidates >>
              request.beam_width >> query_count >> request.memory_limit_mb)) {
            throw std::invalid_argument("malformed native search protocol header");
        }
        request.strategy = parse_strategy(requested_strategy);
        if (query_count == 0 || query_count > 32) {
            throw std::invalid_argument("query count must be between 1 and 32");
        }
        request.queries.reserve(query_count);
        for (std::size_t q = 0; q < query_count; ++q) {
            Query query;
            std::size_t choices = 0;
            if (!(std::cin >> query.weight >> choices) || choices == 0 || choices > 32) {
                throw std::invalid_argument("malformed query header");
            }
            query.options.reserve(choices);
            for (std::size_t i = 0; i < choices; ++i) {
                Option option;
                if (!(std::cin >> option.primitive >> option.predicted_latency_us >>
                      option.physical_memory_mb)) {
                    throw std::invalid_argument("malformed option line");
                }
                query.options.push_back(std::move(option));
            }
            request.queries.push_back(std::move(query));
        }
        std::string trailing;
        if (std::cin >> trailing) {
            throw std::invalid_argument("unexpected trailing input");
        }
        const auto result = search(request);
        std::cout << "OK " << strategy_name(result.strategy) << " "
                  << result.finalists.size() << "\n";
        for (const auto& config : result.finalists) {
            std::cout << "C";
            for (const auto selected : config) std::cout << " " << selected;
            std::cout << "\n";
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "MORPHEUS native search error: " << error.what() << "\n";
        return 2;
    }
}
