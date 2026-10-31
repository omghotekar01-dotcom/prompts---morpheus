#pragma once

// MORPHEUS native C++20 configuration-space search.
// This implementation performs exhaustive, beam and greedy candidate exploration;
// the API adapter supplies per-option estimates bound to the actual workload.
// No workload-specific outcomes are stored in this solver.

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace morpheus::native_search {

enum class Strategy { automatic, exhaustive, beam, greedy };

struct Option {
    std::string primitive;
    double predicted_latency_us = 0.0;
    double physical_memory_mb = 0.0;
};

struct Query {
    double weight = 1.0;
    std::vector<Option> options;
};

struct Request {
    Strategy strategy = Strategy::automatic;
    std::size_t max_candidates = 4096;
    std::size_t beam_width = 128;
    double memory_limit_mb = -1.0; // -1 means no hard memory constraint
    std::vector<Query> queries;
};

using Configuration = std::vector<std::size_t>;

struct Result {
    Strategy strategy;
    std::uint64_t theoretical_configurations;
    std::vector<Configuration> finalists;
    bool truncated = false;
};

inline std::string strategy_name(Strategy strategy) {
    switch (strategy) {
        case Strategy::automatic: return "auto";
        case Strategy::exhaustive: return "exhaustive";
        case Strategy::beam: return "beam";
        case Strategy::greedy: return "greedy";
    }
    throw std::invalid_argument("unknown native search strategy");
}

inline Strategy parse_strategy(const std::string& value) {
    if (value == "auto") return Strategy::automatic;
    if (value == "exhaustive") return Strategy::exhaustive;
    if (value == "beam") return Strategy::beam;
    if (value == "greedy") return Strategy::greedy;
    throw std::invalid_argument("unknown search strategy: " + value);
}

inline void validate(const Request& request) {
    if (request.queries.empty() || request.queries.size() > 32) {
        throw std::invalid_argument("query count must be between 1 and 32");
    }
    if (request.max_candidates == 0 || request.max_candidates > 100000 ||
        request.beam_width == 0 || request.beam_width > 4096) {
        throw std::invalid_argument("candidate budget or beam width is out of bounds");
    }
    if (!std::isfinite(request.memory_limit_mb) ||
        (request.memory_limit_mb != -1.0 && request.memory_limit_mb <= 0.0)) {
        throw std::invalid_argument("memory limit must be positive or -1");
    }
    for (const auto& query : request.queries) {
        if (!std::isfinite(query.weight) || query.weight <= 0.0 ||
            query.options.empty() || query.options.size() > 32) {
            throw std::invalid_argument("every query needs finite positive weight and 1-32 options");
        }
        for (const auto& option : query.options) {
            if (option.primitive.empty() || option.primitive.size() > 128 ||
                !std::isfinite(option.predicted_latency_us) ||
                option.predicted_latency_us < 0.0 ||
                !std::isfinite(option.physical_memory_mb) ||
                option.physical_memory_mb < 0.0) {
                throw std::invalid_argument("invalid native search option");
            }
        }
    }
}

inline std::uint64_t combination_count(const Request& request) {
    std::uint64_t count = 1;
    for (const auto& query : request.queries) {
        const auto choices = static_cast<std::uint64_t>(query.options.size());
        if (count > std::numeric_limits<std::uint64_t>::max() / choices) {
            return std::numeric_limits<std::uint64_t>::max();
        }
        count *= choices;
    }
    return count;
}

inline std::pair<double, double> partial_priority(
    const Request& request, const Configuration& configuration
) {
    double latency_sum = 0.0;
    double weight_sum = 0.0;
    double memory_mb = 0.0;
    for (std::size_t i = 0; i < configuration.size(); ++i) {
        const auto& query = request.queries[i];
        const auto& option = query.options.at(configuration[i]);
        latency_sum += query.weight * option.predicted_latency_us;
        weight_sum += query.weight;
        memory_mb += option.physical_memory_mb;
    }
    double predicted_latency = latency_sum / weight_sum;
    if (request.memory_limit_mb > 0.0 && memory_mb > request.memory_limit_mb) {
        predicted_latency += 1000000.0;
    }
    return {predicted_latency, memory_mb};
}

inline bool prefix_better(
    const Request& request, const Configuration& left, const Configuration& right
) {
    const auto a = partial_priority(request, left);
    const auto b = partial_priority(request, right);
    if (a.first != b.first) return a.first < b.first;
    if (a.second != b.second) return a.second < b.second;
    return left < right; // deterministic because options are in canonical name order
}

inline Result search(const Request& request) {
    validate(request);
    const auto theoretical = combination_count(request);
    Strategy selected = request.strategy;
    if (selected == Strategy::automatic) {
        selected = theoretical <= request.max_candidates ? Strategy::exhaustive : Strategy::beam;
    }
    std::vector<Configuration> finalists;
    if (selected == Strategy::greedy) {
        Configuration prefix;
        for (const auto& query : request.queries) {
            Configuration best;
            for (std::size_t i = 0; i < query.options.size(); ++i) {
                Configuration candidate = prefix;
                candidate.push_back(i);
                if (best.empty() || prefix_better(request, candidate, best)) {
                    best = std::move(candidate);
                }
            }
            prefix = std::move(best);
        }
        finalists.push_back(std::move(prefix));
    } else if (selected == Strategy::beam) {
        finalists.push_back({});
        const auto width = std::min(request.max_candidates, request.beam_width);
        for (const auto& query : request.queries) {
            std::vector<Configuration> expanded;
            expanded.reserve(finalists.size() * query.options.size());
            for (const auto& prefix : finalists) {
                for (std::size_t i = 0; i < query.options.size(); ++i) {
                    auto next = prefix;
                    next.push_back(i);
                    expanded.push_back(std::move(next));
                }
            }
            std::sort(expanded.begin(), expanded.end(),
                      [&](const auto& a, const auto& b) {
                          return prefix_better(request, a, b);
                      });
            if (expanded.size() > width) expanded.resize(width);
            finalists = std::move(expanded);
        }
    } else {
        // Bounded exhaustive search in the same lexicographic order as
        // itertools.product over canonically sorted per-query primitives.
        Configuration current(request.queries.size(), 0);
        const auto limit = std::min<std::uint64_t>(theoretical, request.max_candidates);
        finalists.reserve(static_cast<std::size_t>(limit));
        for (std::uint64_t i = 0; i < limit; ++i) {
            finalists.push_back(current);
            for (std::size_t j = current.size(); j-- > 0;) {
                if (++current[j] < request.queries[j].options.size()) break;
                current[j] = 0;
            }
        }
    }
    const bool truncated = theoretical > finalists.size();
    return {selected, theoretical, std::move(finalists), truncated};
}

} // namespace morpheus::native_search
