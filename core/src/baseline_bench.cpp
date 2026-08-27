#include "morpheus/structures.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

struct Options {
    std::size_t n = 10000;
    std::size_t operations = 50000;
    std::uint64_t seed = 1337;
    std::size_t repetitions = 7;
    std::size_t warmup = 1;
};

struct Stats {
    double median = 0.0;
    double mean = 0.0;
    double stdev = 0.0;
    double minimum = 0.0;
    double maximum = 0.0;
    std::vector<double> samples;
};

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string_view arg = argv[i];
        auto read_size = [&](std::size_t& target) {
            if (i + 1 >= argc) throw std::runtime_error("missing option value");
            target = static_cast<std::size_t>(std::stoull(argv[++i]));
        };
        if (arg == "--n") read_size(options.n);
        else if (arg == "--ops") read_size(options.operations);
        else if (arg == "--seed") {
            if (i + 1 >= argc) throw std::runtime_error("missing seed value");
            options.seed = std::stoull(argv[++i]);
        } else if (arg == "--repetitions") read_size(options.repetitions);
        else if (arg == "--warmup") read_size(options.warmup);
        else throw std::runtime_error("unknown option: " + std::string(arg));
    }
    if (options.n == 0 || options.operations == 0 || options.repetitions == 0) {
        throw std::runtime_error("n, ops and repetitions must be positive");
    }
    if (options.n > 10'000'000 || options.operations > 100'000'000 || options.repetitions > 100 || options.warmup > 20) {
        throw std::runtime_error("benchmark options exceed safety limits");
    }
    return options;
}

std::string compiler_identity() {
#if defined(_MSC_VER)
    return "MSVC-" + std::to_string(_MSC_VER);
#elif defined(__clang__)
    return std::string("Clang-") + __clang_version__;
#elif defined(__GNUC__)
    return std::string("GCC-") + __VERSION__;
#else
    return "unknown";
#endif
}

template <typename Function>
double elapsed_ns_per_operation(std::size_t operations, Function&& function) {
    const auto start = std::chrono::steady_clock::now();
    function();
    const auto stop = std::chrono::steady_clock::now();
    return std::chrono::duration<double, std::nano>(stop - start).count() / static_cast<double>(operations);
}

template <typename Function>
Stats repeat(const Options& options, std::size_t operations, Function&& function) {
    for (std::size_t i = 0; i < options.warmup; ++i) {
        (void)elapsed_ns_per_operation(operations, [&] { function(i, true); });
    }
    std::vector<double> samples;
    samples.reserve(options.repetitions);
    for (std::size_t i = 0; i < options.repetitions; ++i) {
        samples.push_back(elapsed_ns_per_operation(operations, [&] { function(i, false); }));
    }
    auto sorted = samples;
    std::sort(sorted.begin(), sorted.end());
    const double median = sorted.size() % 2 == 0
        ? (sorted[sorted.size() / 2 - 1] + sorted[sorted.size() / 2]) / 2.0
        : sorted[sorted.size() / 2];
    const double mean = std::accumulate(samples.begin(), samples.end(), 0.0) / static_cast<double>(samples.size());
    double variance = 0.0;
    for (const double sample : samples) {
        const double delta = sample - mean;
        variance += delta * delta;
    }
    variance /= static_cast<double>(samples.size());
    return {median, mean, std::sqrt(variance), sorted.front(), sorted.back(), std::move(samples)};
}

void print_stats(std::string_view system, std::string_view operation, const Stats& stats, std::size_t repetitions) {
    std::cout << "    {\"system\":\"" << system
              << "\",\"operation\":\"" << operation
              << "\",\"median_ns\":" << stats.median
              << ",\"mean_ns\":" << stats.mean
              << ",\"stdev_ns\":" << stats.stdev
              << ",\"min_ns\":" << stats.minimum
              << ",\"max_ns\":" << stats.maximum
              << ",\"repetitions\":" << repetitions
              << ",\"samples_ns\":[";
    for (std::size_t i = 0; i < stats.samples.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << stats.samples[i];
    }
    std::cout << "]}";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_options(argc, argv);
        std::mt19937_64 rng(options.seed);
        std::vector<std::uint64_t> keys(options.n);
        std::iota(keys.begin(), keys.end(), std::uint64_t{0});
        std::shuffle(keys.begin(), keys.end(), rng);

        std::uniform_int_distribution<std::size_t> distribution(0, options.n - 1);
        std::vector<std::uint64_t> queries(options.operations);
        for (auto& query : queries) query = keys[distribution(rng)];

        std::uint64_t checksum = 0;

        const auto morpheus_hash_build = repeat(options, options.n, [&](std::size_t repetition, bool) {
            morpheus::RobinHoodHashIndex<std::uint64_t, std::uint64_t> index(options.n * 2);
            for (const auto key : keys) index.insert_or_assign(key, key + repetition);
            checksum += index.size();
        });
        const auto std_hash_build = repeat(options, options.n, [&](std::size_t repetition, bool) {
            std::unordered_map<std::uint64_t, std::uint64_t> index;
            index.reserve(options.n * 2);
            for (const auto key : keys) index.insert_or_assign(key, key + repetition);
            checksum += index.size();
        });
        const auto morpheus_tree_build = repeat(options, options.n, [&](std::size_t repetition, bool) {
            morpheus::OrderedTreeIndex<std::uint64_t, std::uint64_t> index;
            for (const auto key : keys) index.insert_or_assign(key, key + repetition);
            checksum += index.size();
        });
        const auto std_tree_build = repeat(options, options.n, [&](std::size_t repetition, bool) {
            std::map<std::uint64_t, std::uint64_t> index;
            for (const auto key : keys) index.insert_or_assign(key, key + repetition);
            checksum += index.size();
        });

        morpheus::RobinHoodHashIndex<std::uint64_t, std::uint64_t> morpheus_hash(options.n * 2);
        std::unordered_map<std::uint64_t, std::uint64_t> std_hash;
        std_hash.reserve(options.n * 2);
        morpheus::OrderedTreeIndex<std::uint64_t, std::uint64_t> morpheus_tree;
        std::map<std::uint64_t, std::uint64_t> std_tree;
        for (const auto key : keys) {
            morpheus_hash.insert_or_assign(key, key * 3);
            std_hash.insert_or_assign(key, key * 3);
            morpheus_tree.insert_or_assign(key, key * 3);
            std_tree.insert_or_assign(key, key * 3);
        }

        const auto morpheus_hash_lookup = repeat(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) if (const auto* value = morpheus_hash.find(key)) checksum += *value;
        });
        const auto std_hash_lookup = repeat(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) {
                const auto it = std_hash.find(key);
                if (it != std_hash.end()) checksum += it->second;
            }
        });
        const auto morpheus_tree_lookup = repeat(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) if (const auto* value = morpheus_tree.find(key)) checksum += *value;
        });
        const auto std_tree_lookup = repeat(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) {
                const auto it = std_tree.find(key);
                if (it != std_tree.end()) checksum += it->second;
            }
        });

        const auto morpheus_tree_range = repeat(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) {
                const auto high = std::min<std::uint64_t>(key + 8, options.n - 1);
                const auto values = morpheus_tree.range(key, high);
                checksum += values.size();
            }
        });
        const auto std_tree_range = repeat(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) {
                const auto high = std::min<std::uint64_t>(key + 8, options.n - 1);
                std::size_t count = 0;
                for (auto it = std_tree.lower_bound(key); it != std_tree.end() && it->first <= high; ++it) ++count;
                checksum += count;
            }
        });

        std::cout << std::fixed << std::setprecision(3);
        std::cout << "{\n"
                  << "  \"schema_version\":1,\n"
                  << "  \"protocol\":\"morpheus-baseline-bench-v1\",\n"
                  << "  \"evidence_state\":\"MEASURED_LOCAL_PROCESS_REPEATED\",\n"
                  << "  \"truth_note\":\"Local paired standard-library baseline measurement; not a state-of-the-art comparison.\",\n"
                  << "  \"compiler\":\"" << compiler_identity() << "\",\n"
                  << "  \"cplusplus\":" << __cplusplus << ",\n"
                  << "  \"n\":" << options.n << ",\n"
                  << "  \"operations\":" << options.operations << ",\n"
                  << "  \"seed\":" << options.seed << ",\n"
                  << "  \"repetitions\":" << options.repetitions << ",\n"
                  << "  \"warmup_repetitions\":" << options.warmup << ",\n"
                  << "  \"checksum\":" << checksum << ",\n"
                  << "  \"measurements\":[\n";

        struct Measurement { std::string_view system; std::string_view operation; const Stats* stats; };
        const std::vector<Measurement> measurements = {
            {"morpheus_robin_hood_hash", "build", &morpheus_hash_build},
            {"std_unordered_map", "build", &std_hash_build},
            {"morpheus_bplus_tree", "build", &morpheus_tree_build},
            {"std_map", "build", &std_tree_build},
            {"morpheus_robin_hood_hash", "point_lookup", &morpheus_hash_lookup},
            {"std_unordered_map", "point_lookup", &std_hash_lookup},
            {"morpheus_bplus_tree", "point_lookup", &morpheus_tree_lookup},
            {"std_map", "point_lookup", &std_tree_lookup},
            {"morpheus_bplus_tree", "range_scan", &morpheus_tree_range},
            {"std_map", "range_scan", &std_tree_range},
        };
        for (std::size_t i = 0; i < measurements.size(); ++i) {
            print_stats(measurements[i].system, measurements[i].operation, *measurements[i].stats, options.repetitions);
            std::cout << (i + 1 == measurements.size() ? "\n" : ",\n");
        }
        std::cout << "  ]\n}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "morpheus_baseline_bench: " << error.what() << '\n';
        return 2;
    }
}
