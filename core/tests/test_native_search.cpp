#include "morpheus/native_search.hpp"

#ifdef NDEBUG
#undef NDEBUG // Keep C++ correctness tests active in Release builds.
#endif
#include <cassert>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

using namespace morpheus::native_search;

int main() {
    Request input;
    input.queries = {
        {0.9, {{"robin_hood_hash", 0.1, 12.0}, {"ordered_tree", 0.5, 5.0}}},
        {0.1, {{"sorted_array", 0.2, 6.0}, {"ordered_tree", 0.3, 4.0}}},
    };
    input.max_candidates = 64;
    const auto exhaustive = search(input);
    assert(exhaustive.strategy == Strategy::exhaustive);
    assert(exhaustive.theoretical_configurations == 4);
    assert(!exhaustive.truncated);
    assert(exhaustive.finalists.size() == 4);
    assert(exhaustive.finalists.front() == Configuration({0, 0}));
    assert(exhaustive.finalists.back() == Configuration({1, 1}));

    input.strategy = Strategy::greedy;
    const auto greedy = search(input);
    assert(greedy.finalists.size() == 1);
    assert(greedy.finalists[0] == Configuration({0, 0}));
    assert(greedy.truncated);

    // Changing actual workload weights can change the native search outcome;
    // there are no fixed rule-to-answer mappings in this implementation.
    input.strategy = Strategy::beam;
    input.beam_width = 1;
    input.memory_limit_mb = 10.0;
    const auto low_memory = search(input);
    assert(low_memory.finalists.size() == 1);
    assert(low_memory.finalists[0] == Configuration({1, 1}));
    assert(low_memory.truncated);

    // A different memory constraint changes the candidate ranking.
    input.memory_limit_mb = 64.0;
    const auto generous_memory = search(input);
    assert(generous_memory.finalists[0] == Configuration({0, 0}));

    input.strategy = Strategy::exhaustive;
    input.max_candidates = 2;
    const auto limited = search(input);
    assert(limited.finalists.size() == 2);
    assert(limited.truncated);

    input.queries[0].weight = std::numeric_limits<double>::infinity();
    bool rejected = false;
    try {
        (void)search(input);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    // Overflow is bounded without enumerating impossible state spaces.
    Request huge;
    huge.strategy = Strategy::automatic;
    huge.max_candidates = 8;
    huge.beam_width = 3;
    for (int i = 0; i < 32; ++i) {
        Query q;
        for (int j = 0; j < 6; ++j) {
            q.options.push_back({"p" + std::to_string(j), static_cast<double>(j + 1), 1.0});
        }
        huge.queries.push_back(std::move(q));
    }
    const auto large = search(huge);
    assert(large.strategy == Strategy::beam);
    assert(large.theoretical_configurations == std::numeric_limits<std::uint64_t>::max());
    assert(large.finalists.size() == 3);
    assert(large.truncated);
}
