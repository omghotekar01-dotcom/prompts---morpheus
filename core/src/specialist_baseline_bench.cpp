#include "morpheus/bplus_tree.hpp"
#include "morpheus/structures.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#if __has_include(<boost/unordered/unordered_flat_map.hpp>)
#define MORPHEUS_HAVE_BOOST_UNORDERED_FLAT_MAP 1
#include <boost/unordered/unordered_flat_map.hpp>
#else
#define MORPHEUS_HAVE_BOOST_UNORDERED_FLAT_MAP 0
#endif

#if __has_include(<boost/container/flat_map.hpp>)
#define MORPHEUS_HAVE_BOOST_FLAT_MAP 1
#include <boost/container/flat_map.hpp>
#else
#define MORPHEUS_HAVE_BOOST_FLAT_MAP 0
#endif

namespace {

struct Options {
    std::size_t n = 10000;
    std::size_t operations = 50000;
    std::uint64_t seed = 1337;
    std::size_t repetitions = 7;
    std::size_t warmup = 1;
    bool require_specialists = false;
};

struct Stats {
    double median = 0.0;
    double mean = 0.0;
    double stdev = 0.0;
    double minimum = 0.0;
    double maximum = 0.0;
    std::vector<double> samples;
};

struct Measurement {
    std::string system;
    std::string operation;
    std::string family;
    Stats stats;
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
        else if (arg == "--require-specialists") options.require_specialists = true;
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

void print_measurement(const Measurement& measurement) {
    const auto& stats = measurement.stats;
    std::cout << "    {\"system\":\"" << measurement.system
              << "\",\"operation\":\"" << measurement.operation
              << "\",\"family\":\"" << measurement.family
              << "\",\"median_ns\":" << stats.median
              << ",\"mean_ns\":" << stats.mean
              << ",\"stdev_ns\":" << stats.stdev
              << ",\"min_ns\":" << stats.minimum
              << ",\"max_ns\":" << stats.maximum
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
        constexpr bool have_boost_hash = MORPHEUS_HAVE_BOOST_UNORDERED_FLAT_MAP != 0;
        constexpr bool have_boost_flat_map = MORPHEUS_HAVE_BOOST_FLAT_MAP != 0;
        if (options.require_specialists && (!have_boost_hash || !have_boost_flat_map)) {
            throw std::runtime_error("required Boost specialist headers are unavailable on this machine");
        }

        std::mt19937_64 rng(options.seed);
        std::vector<std::uint64_t> keys(options.n);
        std::iota(keys.begin(), keys.end(), std::uint64_t{0});
        std::shuffle(keys.begin(), keys.end(), rng);
        std::uniform_int_distribution<std::size_t> distribution(0, options.n - 1);
        std::vector<std::uint64_t> queries(options.operations);
        for (auto& query : queries) query = keys[distribution(rng)];

        std::uint64_t checksum = 0;
        std::vector<Measurement> measurements;

        measurements.push_back({
            "morpheus_robin_hood_hash",
            "build",
            "open_addressing_hash",
            repeat(options, options.n, [&](std::size_t repetition, bool) {
                morpheus::RobinHoodHashIndex<std::uint64_t, std::uint64_t> index(options.n * 2);
                for (const auto key : keys) index.insert_or_assign(key, key + repetition);
                checksum += index.size();
            }),
        });

        measurements.push_back({
            "morpheus_bplus_tree_rebalanced",
            "build",
            "ordered_tree",
            repeat(options, options.n, [&](std::size_t repetition, bool) {
                morpheus::BPlusTreeIndex<std::uint64_t, std::uint64_t> index;
                for (const auto key : keys) index.insert_or_assign(key, key + repetition);
                checksum += index.size();
            }),
        });

        morpheus::RobinHoodHashIndex<std::uint64_t, std::uint64_t> morpheus_hash(options.n * 2);
        morpheus::BPlusTreeIndex<std::uint64_t, std::uint64_t> morpheus_tree;
        for (const auto key : keys) {
            morpheus_hash.insert_or_assign(key, key * 3);
            morpheus_tree.insert_or_assign(key, key * 3);
        }

        measurements.push_back({
            "morpheus_robin_hood_hash",
            "point_lookup",
            "open_addressing_hash",
            repeat(options, options.operations, [&](std::size_t, bool) {
                for (const auto key : queries) if (const auto* value = morpheus_hash.find(key)) checksum += *value;
            }),
        });
        measurements.push_back({
            "morpheus_bplus_tree_rebalanced",
            "point_lookup",
            "ordered_tree",
            repeat(options, options.operations, [&](std::size_t, bool) {
                for (const auto key : queries) if (const auto* value = morpheus_tree.find(key)) checksum += *value;
            }),
        });
        measurements.push_back({
            "morpheus_bplus_tree_rebalanced",
            "range_scan",
            "ordered_tree",
            repeat(options, options.operations, [&](std::size_t, bool) {
                for (const auto key : queries) {
                    const auto high = std::min<std::uint64_t>(key + 8, options.n - 1);
                    checksum += morpheus_tree.range(key, high).size();
                }
            }),
        });

#if MORPHEUS_HAVE_BOOST_UNORDERED_FLAT_MAP
        measurements.push_back({
            "boost_unordered_flat_map",
            "build",
            "open_addressing_hash_specialist",
            repeat(options, options.n, [&](std::size_t repetition, bool) {
                boost::unordered_flat_map<std::uint64_t, std::uint64_t> index;
                index.reserve(options.n);
                for (const auto key : keys) index.insert_or_assign(key, key + repetition);
                checksum += index.size();
            }),
        });
        boost::unordered_flat_map<std::uint64_t, std::uint64_t> boost_hash;
        boost_hash.reserve(options.n);
        for (const auto key : keys) boost_hash.insert_or_assign(key, key * 3);
        measurements.push_back({
            "boost_unordered_flat_map",
            "point_lookup",
            "open_addressing_hash_specialist",
            repeat(options, options.operations, [&](std::size_t, bool) {
                for (const auto key : queries) {
                    const auto it = boost_hash.find(key);
                    if (it != boost_hash.end()) checksum += it->second;
                }
            }),
        });
#endif

#if MORPHEUS_HAVE_BOOST_FLAT_MAP
        measurements.push_back({
            "boost_container_flat_map",
            "build",
            "sorted_contiguous_map_specialist",
            repeat(options, options.n, [&](std::size_t repetition, bool) {
                boost::container::flat_map<std::uint64_t, std::uint64_t> index;
                index.reserve(options.n);
                for (const auto key : keys) index.insert_or_assign(key, key + repetition);
                checksum += index.size();
            }),
        });
        boost::container::flat_map<std::uint64_t, std::uint64_t> boost_ordered;
        boost_ordered.reserve(options.n);
        for (const auto key : keys) boost_ordered.insert_or_assign(key, key * 3);
        measurements.push_back({
            "boost_container_flat_map",
            "point_lookup",
            "sorted_contiguous_map_specialist",
            repeat(options, options.operations, [&](std::size_t, bool) {
                for (const auto key : queries) {
                    const auto it = boost_ordered.find(key);
                    if (it != boost_ordered.end()) checksum += it->second;
                }
            }),
        });
        measurements.push_back({
            "boost_container_flat_map",
            "range_scan",
            "sorted_contiguous_map_specialist",
            repeat(options, options.operations, [&](std::size_t, bool) {
                for (const auto key : queries) {
                    const auto high = std::min<std::uint64_t>(key + 8, options.n - 1);
                    std::size_t count = 0;
                    for (auto it = boost_ordered.lower_bound(key); it != boost_ordered.end() && it->first <= high; ++it) ++count;
                    checksum += count;
                }
            }),
        });
#endif

        std::cout << std::fixed << std::setprecision(3);
        std::cout << "{\n"
                  << "  \"schema_version\":1,\n"
                  << "  \"protocol\":\"morpheus-specialist-baseline-v1\",\n"
                  << "  \"evidence_state\":\"MEASURED_LOCAL_PROCESS_REPEATED\",\n"
                  << "  \"truth_note\":\"Paired local specialist-container comparison. Availability is toolchain-dependent; results are not universal or publication-grade without a controlled campaign.\",\n"
                  << "  \"compiler\":\"" << compiler_identity() << "\",\n"
                  << "  \"cplusplus\":" << __cplusplus << ",\n"
                  << "  \"n\":" << options.n << ",\n"
                  << "  \"operations\":" << options.operations << ",\n"
                  << "  \"seed\":" << options.seed << ",\n"
                  << "  \"repetitions\":" << options.repetitions << ",\n"
                  << "  \"warmup_repetitions\":" << options.warmup << ",\n"
                  << "  \"specialists\":{\"boost_unordered_flat_map\":" << (have_boost_hash ? "true" : "false")
                  << ",\"boost_container_flat_map\":" << (have_boost_flat_map ? "true" : "false") << "},\n"
                  << "  \"checksum\":" << checksum << ",\n"
                  << "  \"measurements\":[\n";
        for (std::size_t i = 0; i < measurements.size(); ++i) {
            print_measurement(measurements[i]);
            std::cout << (i + 1 == measurements.size() ? "\n" : ",\n");
        }
        std::cout << "  ]\n}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "morpheus_specialist_baseline_bench: " << error.what() << '\n';
        return 2;
    }
}
