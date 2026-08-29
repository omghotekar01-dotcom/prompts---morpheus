#include "morpheus/bplus_tree.hpp"
#include "morpheus/compressed_bitmap.hpp"
#include "morpheus/mutable_indices.hpp"
#include "morpheus/structures.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

constexpr std::string_view HASH_IMPL = "morpheus.RobinHoodHashIndex.v1";
constexpr std::string_view TREE_IMPL = "morpheus.BPlusTreeIndex.rebalanced.v1";
constexpr std::string_view SORTED_IMPL = "morpheus.MutableSortedArrayIndex.v1";
constexpr std::string_view TRIE_IMPL = "morpheus.MutableMultiPrefixTrie.v1";
constexpr std::string_view BITMAP_IMPL = "morpheus.CompressedBitmapFilterIndex.adaptive32.v1";

struct Options {
    std::size_t n = 10000;
    std::size_t operations = 50000;
    std::uint64_t seed = 1337;
    std::size_t repetitions = 7;
    std::size_t warmup = 1;
    std::vector<std::string> distributions{"uniform", "sequential", "hotspot", "zipf"};
    double zipf_theta = 0.99;
    double hotspot_fraction = 0.10;
    double hotspot_probability = 0.80;
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
    std::string primitive;
    std::string implementation_id;
    std::string operation;
    std::string distribution;
    Stats stats;
};

std::vector<std::string> split_csv(std::string_view text) {
    std::vector<std::string> values;
    std::size_t start = 0;
    while (start <= text.size()) {
        const auto comma = text.find(',', start);
        const auto end = comma == std::string_view::npos ? text.size() : comma;
        if (end > start) values.emplace_back(text.substr(start, end - start));
        if (comma == std::string_view::npos) break;
        start = comma + 1;
    }
    return values;
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string_view arg = argv[i];
        auto require_value = [&]() -> std::string_view {
            if (i + 1 >= argc) throw std::runtime_error("missing argument value for " + std::string(arg));
            return argv[++i];
        };
        if (arg == "--n") options.n = static_cast<std::size_t>(std::stoull(std::string(require_value())));
        else if (arg == "--ops") options.operations = static_cast<std::size_t>(std::stoull(std::string(require_value())));
        else if (arg == "--seed") options.seed = std::stoull(std::string(require_value()));
        else if (arg == "--repetitions") options.repetitions = static_cast<std::size_t>(std::stoull(std::string(require_value())));
        else if (arg == "--warmup") options.warmup = static_cast<std::size_t>(std::stoull(std::string(require_value())));
        else if (arg == "--distributions") options.distributions = split_csv(require_value());
        else if (arg == "--zipf-theta") options.zipf_theta = std::stod(std::string(require_value()));
        else if (arg == "--hotspot-fraction") options.hotspot_fraction = std::stod(std::string(require_value()));
        else if (arg == "--hotspot-probability") options.hotspot_probability = std::stod(std::string(require_value()));
        else throw std::runtime_error("unknown option: " + std::string(arg));
    }

    if (options.n < 2 || options.operations == 0 || options.repetitions == 0) {
        throw std::runtime_error("n must be >=2 and ops/repetitions must be positive");
    }
    if (options.n > static_cast<std::size_t>(std::numeric_limits<std::uint32_t>::max())) {
        throw std::runtime_error("n exceeds 32-bit stable-slot limit");
    }
    if (options.repetitions > 100 || options.warmup > 20) {
        throw std::runtime_error("repetitions/warmup exceed safety limits");
    }
    if (options.zipf_theta <= 0.0 || options.zipf_theta > 4.0) {
        throw std::runtime_error("zipf theta must be in (0,4]");
    }
    if (options.hotspot_fraction <= 0.0 || options.hotspot_fraction > 1.0) {
        throw std::runtime_error("hotspot fraction must be in (0,1]");
    }
    if (options.hotspot_probability <= 0.0 || options.hotspot_probability > 1.0) {
        throw std::runtime_error("hotspot probability must be in (0,1]");
    }
    if (options.distributions.empty()) throw std::runtime_error("at least one distribution is required");
    for (const auto& distribution : options.distributions) {
        if (distribution != "uniform" && distribution != "sequential" && distribution != "hotspot" && distribution != "zipf") {
            throw std::runtime_error("unsupported distribution: " + distribution);
        }
    }
    std::sort(options.distributions.begin(), options.distributions.end());
    options.distributions.erase(std::unique(options.distributions.begin(), options.distributions.end()), options.distributions.end());
    return options;
}

template <typename Function>
double elapsed_ns_per_operation(std::size_t operations, Function&& function) {
    const auto start = std::chrono::steady_clock::now();
    function();
    const auto stop = std::chrono::steady_clock::now();
    return std::chrono::duration<double, std::nano>(stop - start).count() / static_cast<double>(operations);
}

template <typename Function>
Stats repeat_measurement(const Options& options, std::size_t operations, Function&& function) {
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

std::vector<std::uint64_t> build_query_stream(const Options& options, std::string_view kind, std::uint64_t seed_offset) {
    std::vector<std::uint64_t> stream(options.operations);
    std::mt19937_64 rng(options.seed + seed_offset);

    if (kind == "sequential") {
        for (std::size_t i = 0; i < stream.size(); ++i) stream[i] = static_cast<std::uint64_t>(i % options.n);
        return stream;
    }

    if (kind == "uniform") {
        std::uniform_int_distribution<std::uint64_t> uniform(0, static_cast<std::uint64_t>(options.n - 1));
        for (auto& value : stream) value = uniform(rng);
        return stream;
    }

    if (kind == "hotspot") {
        const auto hot_count = std::max<std::size_t>(1, static_cast<std::size_t>(std::ceil(options.n * options.hotspot_fraction)));
        std::bernoulli_distribution choose_hot(options.hotspot_probability);
        std::uniform_int_distribution<std::uint64_t> hot(0, static_cast<std::uint64_t>(hot_count - 1));
        std::uniform_int_distribution<std::uint64_t> cold(
            static_cast<std::uint64_t>(std::min(hot_count, options.n - 1)),
            static_cast<std::uint64_t>(options.n - 1)
        );
        for (auto& value : stream) {
            if (choose_hot(rng) || hot_count >= options.n) value = hot(rng);
            else value = cold(rng);
        }
        return stream;
    }

    if (kind == "zipf") {
        std::vector<double> cdf(options.n);
        double total = 0.0;
        for (std::size_t i = 0; i < options.n; ++i) total += 1.0 / std::pow(static_cast<double>(i + 1), options.zipf_theta);
        double running = 0.0;
        for (std::size_t i = 0; i < options.n; ++i) {
            running += (1.0 / std::pow(static_cast<double>(i + 1), options.zipf_theta)) / total;
            cdf[i] = running;
        }
        cdf.back() = 1.0;
        std::uniform_real_distribution<double> uniform(0.0, 1.0);
        for (auto& value : stream) {
            const double sample = uniform(rng);
            value = static_cast<std::uint64_t>(std::lower_bound(cdf.begin(), cdf.end(), sample) - cdf.begin());
        }
        return stream;
    }

    throw std::runtime_error("unreachable distribution kind");
}

std::string distribution_json(const Options& options, std::string_view kind) {
    if (kind == "zipf") {
        return "{\"kind\":\"zipf\",\"zipf_theta\":" + std::to_string(options.zipf_theta) + "}";
    }
    if (kind == "hotspot") {
        return "{\"kind\":\"hotspot\",\"hotspot_fraction\":" + std::to_string(options.hotspot_fraction)
            + ",\"hotspot_probability\":" + std::to_string(options.hotspot_probability) + "}";
    }
    return "{\"kind\":\"" + std::string(kind) + "\"}";
}

std::string compiler_identity() {
#if defined(__clang__)
    return std::string("Clang ") + __clang_version__;
#elif defined(_MSC_VER)
    return std::string("MSVC ") + std::to_string(_MSC_VER);
#elif defined(__GNUC__)
    return std::string("GCC ") + __VERSION__;
#else
    return "unknown-cxx-compiler";
#endif
}

void print_measurement(const Options& options, const Measurement& measurement) {
    const auto& stats = measurement.stats;
    std::cout << "    {\"primitive\":\"" << measurement.primitive
              << "\",\"implementation_id\":\"" << measurement.implementation_id
              << "\",\"operation\":\"" << measurement.operation
              << "\",\"access_distribution\":" << distribution_json(options, measurement.distribution)
              << ",\"ns_per_op\":" << stats.median
              << ",\"repetitions\":" << options.repetitions
              << ",\"stdev_ns\":" << stats.stdev
              << ",\"mean_ns\":" << stats.mean
              << ",\"median_ns\":" << stats.median
              << ",\"min_ns\":" << stats.minimum
              << ",\"max_ns\":" << stats.maximum
              << ",\"samples_ns\":[";
    for (std::size_t i = 0; i < stats.samples.size(); ++i) {
        if (i != 0) std::cout << ',';
        std::cout << stats.samples[i];
    }
    std::cout << "]}";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const auto options = parse_options(argc, argv);
        std::mt19937_64 insertion_rng(options.seed);
        std::vector<std::uint64_t> keys(options.n);
        std::iota(keys.begin(), keys.end(), std::uint64_t{0});
        std::shuffle(keys.begin(), keys.end(), insertion_rng);

        std::vector<std::uint32_t> slot_for_key(options.n);
        for (std::size_t i = 0; i < keys.size(); ++i) slot_for_key[static_cast<std::size_t>(keys[i])] = static_cast<std::uint32_t>(i);
        std::vector<std::string> string_keys;
        string_keys.reserve(options.n);
        for (std::size_t i = 0; i < options.n; ++i) string_keys.push_back("key-" + std::to_string(i));

        morpheus::RobinHoodHashIndex<std::uint64_t, std::size_t> hash(options.n * 2);
        morpheus::BPlusTreeIndex<std::uint64_t, std::size_t> tree;
        morpheus::MutableSortedArrayIndex<std::uint64_t, std::size_t> sorted;
        morpheus::CompressedBitmapFilterIndex<std::uint64_t, std::uint32_t> bitmap;
        morpheus::MutableMultiPrefixTrie<std::size_t> trie;
        for (std::size_t i = 0; i < keys.size(); ++i) {
            hash.insert_or_assign(keys[i], i);
            tree.insert_or_assign(keys[i], i);
            sorted.insert_or_assign(keys[i], i);
            bitmap.add(keys[i] % 128, static_cast<std::uint32_t>(i));
            trie.add(string_keys[i], i);
        }

        std::uint64_t checksum = 0;
        std::vector<Measurement> measurements;
        std::uint64_t distribution_seed_offset = 1;
        for (const auto& distribution : options.distributions) {
            const auto queries = build_query_stream(options, distribution, distribution_seed_offset++ * 100003ULL);

            measurements.push_back({"robin_hood_hash", std::string(HASH_IMPL), "point_lookup", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t, bool) {
                    for (const auto key : queries) if (const auto* value = hash.find(key)) checksum += *value;
                })});
            measurements.push_back({"ordered_tree", std::string(TREE_IMPL), "point_lookup", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t, bool) {
                    for (const auto key : queries) if (const auto* value = tree.find(key)) checksum += *value;
                })});
            measurements.push_back({"sorted_array", std::string(SORTED_IMPL), "point_lookup", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t, bool) {
                    for (const auto key : queries) if (const auto* value = sorted.find(key)) checksum += *value;
                })});
            measurements.push_back({"radix_trie", std::string(TRIE_IMPL), "point_lookup", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t, bool) {
                    for (const auto key : queries) if (const auto* value = trie.find(string_keys[static_cast<std::size_t>(key)])) checksum += *value;
                })});
            measurements.push_back({"ordered_tree", std::string(TREE_IMPL), "range_scan", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t, bool) {
                    for (const auto key : queries) {
                        const auto high = std::min<std::uint64_t>(key + 8, options.n - 1);
                        checksum += tree.range(key, high).size();
                    }
                })});
            measurements.push_back({"sorted_array", std::string(SORTED_IMPL), "range_scan", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t, bool) {
                    for (const auto key : queries) {
                        const auto high = std::min<std::uint64_t>(key + 8, options.n - 1);
                        checksum += sorted.range(key, high).size();
                    }
                })});
            measurements.push_back({"bitmap", std::string(BITMAP_IMPL), "filter", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t, bool) {
                    for (const auto key : queries) checksum += bitmap.filter(key % 128).size();
                })});
            measurements.push_back({"radix_trie", std::string(TRIE_IMPL), "prefix_search", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t, bool) {
                    for (const auto key : queries) {
                        const auto& value = string_keys[static_cast<std::size_t>(key)];
                        checksum += trie.prefix_search(value.substr(0, std::min<std::size_t>(6, value.size())), 16).size();
                    }
                })});

            measurements.push_back({"robin_hood_hash", std::string(HASH_IMPL), "update", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
                    for (const auto key : queries) hash.insert_or_assign(key, static_cast<std::size_t>(key + repetition));
                    checksum += hash.size();
                })});
            measurements.push_back({"ordered_tree", std::string(TREE_IMPL), "update", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
                    for (const auto key : queries) tree.insert_or_assign(key, static_cast<std::size_t>(key + repetition));
                    checksum += tree.size();
                })});
            measurements.push_back({"sorted_array", std::string(SORTED_IMPL), "update", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
                    for (const auto key : queries) sorted.insert_or_assign(key, static_cast<std::size_t>(key + repetition));
                    checksum += sorted.size();
                })});
            measurements.push_back({"bitmap", std::string(BITMAP_IMPL), "update", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
                    for (const auto key : queries) {
                        const auto slot = slot_for_key[static_cast<std::size_t>(key)];
                        const auto old_category = key % 128;
                        const auto new_category = (old_category + 1 + repetition) % 128;
                        if (!bitmap.remove(old_category, slot)) throw std::runtime_error("bitmap source posting missing");
                        bitmap.add(new_category, slot);
                        if (!bitmap.remove(new_category, slot)) throw std::runtime_error("bitmap temporary posting missing");
                        bitmap.add(old_category, slot);
                    }
                    checksum += bitmap.filter(0).size();
                })});
            measurements.push_back({"radix_trie", std::string(TRIE_IMPL), "update", distribution,
                repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
                    for (const auto key : queries) {
                        const auto index = static_cast<std::size_t>(key);
                        trie.remove(string_keys[index], index);
                        trie.add(string_keys[index], index + repetition + options.n);
                        trie.remove(string_keys[index], index + repetition + options.n);
                        trie.add(string_keys[index], index);
                    }
                    checksum += trie.key_count();
                })});
        }

        std::cout << std::fixed << std::setprecision(6);
        std::cout << "{\n"
                  << "  \"profile_id\": \"local-dist-" << options.seed << '-' << options.n << '-' << options.operations << "\",\n"
                  << "  \"schema_version\": 4,\n"
                  << "  \"evidence_state\": \"MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_AND_DISTRIBUTION_BOUND\",\n"
                  << "  \"protocol\": \"morpheus-distribution-calibration-v1\",\n"
                  << "  \"distribution_protocol\": \"morpheus-access-distribution-v1\",\n"
                  << "  \"truth_note\": \"Access streams are generated before timed regions and every measurement is bound to exact physical implementation and declared distribution parameters. This remains machine-local primitive evidence, not end-to-end candidate performance.\",\n"
                  << "  \"n\": " << options.n << ",\n"
                  << "  \"operations\": " << options.operations << ",\n"
                  << "  \"seed\": " << options.seed << ",\n"
                  << "  \"repetitions\": " << options.repetitions << ",\n"
                  << "  \"warmup_repetitions\": " << options.warmup << ",\n"
                  << "  \"checksum\": " << checksum << ",\n"
                  << "  \"machine\": {\"compiler\":\"" << compiler_identity() << "\",\"cplusplus\":\"" << __cplusplus << "\"},\n"
                  << "  \"measurements\": [\n";
        for (std::size_t i = 0; i < measurements.size(); ++i) {
            print_measurement(options, measurements[i]);
            std::cout << (i + 1 == measurements.size() ? "\n" : ",\n");
        }
        std::cout << "  ]\n}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "morpheus_distribution_calibrate: " << error.what() << '\n';
        return 2;
    }
}
