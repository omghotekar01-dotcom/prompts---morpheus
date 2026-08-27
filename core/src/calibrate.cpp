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
#include <tuple>
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
            if (i + 1 >= argc) throw std::runtime_error("missing argument value");
            target = static_cast<std::size_t>(std::stoull(argv[++i]));
        };
        if (arg == "--n") {
            read_size(options.n);
        } else if (arg == "--ops") {
            read_size(options.operations);
        } else if (arg == "--seed") {
            if (i + 1 >= argc) throw std::runtime_error("missing seed value");
            options.seed = std::stoull(argv[++i]);
        } else if (arg == "--repetitions") {
            read_size(options.repetitions);
        } else if (arg == "--warmup") {
            read_size(options.warmup);
        } else {
            throw std::runtime_error("unknown option: " + std::string(arg));
        }
    }
    if (options.n == 0 || options.operations == 0 || options.repetitions == 0) {
        throw std::runtime_error("n, ops and repetitions must be positive");
    }
    if (options.repetitions > 100 || options.warmup > 20) {
        throw std::runtime_error("repetitions/warmup exceed safety limits");
    }
    return options;
}

template <typename Function>
double elapsed_ns_per_operation(std::size_t operations, Function&& function) {
    const auto start = std::chrono::steady_clock::now();
    function();
    const auto stop = std::chrono::steady_clock::now();
    const auto elapsed = std::chrono::duration<double, std::nano>(stop - start).count();
    return elapsed / static_cast<double>(operations);
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

    std::vector<double> sorted = samples;
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

    return Stats{
        median,
        mean,
        std::sqrt(variance),
        sorted.front(),
        sorted.back(),
        std::move(samples),
    };
}

std::string json_escape(std::string_view input) {
    std::string out;
    out.reserve(input.size());
    for (const char ch : input) {
        switch (ch) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default: out += ch; break;
        }
    }
    return out;
}

void print_measurement(std::string_view primitive, std::string_view operation, const Stats& stats, std::size_t repetitions) {
    std::cout << "    {\"primitive\":\"" << primitive
              << "\",\"operation\":\"" << operation
              << "\",\"ns_per_op\":" << stats.median
              << ",\"repetitions\":" << repetitions
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
        std::mt19937_64 rng(options.seed);

        std::vector<std::uint64_t> keys(options.n);
        std::iota(keys.begin(), keys.end(), std::uint64_t{0});
        std::shuffle(keys.begin(), keys.end(), rng);

        std::vector<std::uint64_t> queries(options.operations);
        std::uniform_int_distribution<std::size_t> distribution(0, options.n - 1);
        for (auto& query : queries) query = keys[distribution(rng)];

        std::vector<std::pair<std::uint64_t, std::uint64_t>> rows;
        rows.reserve(options.n);
        for (const auto key : keys) rows.emplace_back(key, key * 2);

        std::vector<std::string> string_keys;
        string_keys.reserve(options.n);
        for (std::size_t i = 0; i < options.n; ++i) {
            string_keys.push_back("key-" + std::to_string(i));
        }

        std::uint64_t checksum = 0;

        const auto hash_build = repeat_measurement(options, options.n, [&](std::size_t repetition, bool) {
            morpheus::RobinHoodHashIndex<std::uint64_t, std::uint64_t> index(options.n * 2);
            for (const auto key : keys) index.insert_or_assign(key, key * 2 + repetition);
            checksum += index.size();
        });

        const auto tree_build = repeat_measurement(options, options.n, [&](std::size_t repetition, bool) {
            morpheus::OrderedTreeIndex<std::uint64_t, std::uint64_t> index;
            for (const auto key : keys) index.insert_or_assign(key, key * 2 + repetition);
            checksum += index.size();
        });

        const auto sorted_build = repeat_measurement(options, options.n, [&](std::size_t, bool) {
            morpheus::SortedArrayIndex<std::uint64_t, std::uint64_t> index;
            index.bulk_load(rows);
            checksum += index.size();
        });

        const auto bitmap_build = repeat_measurement(options, options.n, [&](std::size_t, bool) {
            morpheus::BitmapFilterIndex<std::uint64_t, std::uint64_t> index;
            for (std::size_t i = 0; i < keys.size(); ++i) index.add(keys[i] % 128, i);
            checksum += index.filter(0).size();
        });

        const auto trie_build = repeat_measurement(options, options.n, [&](std::size_t repetition, bool) {
            morpheus::PrefixTrie<std::uint64_t> index;
            for (std::size_t i = 0; i < string_keys.size(); ++i) index.insert_or_assign(string_keys[i], i + repetition);
            checksum += index.size();
        });

        morpheus::RobinHoodHashIndex<std::uint64_t, std::uint64_t> hash(options.n * 2);
        morpheus::OrderedTreeIndex<std::uint64_t, std::uint64_t> tree;
        morpheus::SortedArrayIndex<std::uint64_t, std::uint64_t> sorted;
        morpheus::BitmapFilterIndex<std::uint64_t, std::uint64_t> bitmap;
        morpheus::PrefixTrie<std::uint64_t> trie;
        for (const auto key : keys) {
            hash.insert_or_assign(key, key * 2);
            tree.insert_or_assign(key, key * 2);
        }
        sorted.bulk_load(rows);
        for (std::size_t i = 0; i < keys.size(); ++i) bitmap.add(keys[i] % 128, i);
        for (std::size_t i = 0; i < string_keys.size(); ++i) trie.insert_or_assign(string_keys[i], i);

        const auto hash_lookup = repeat_measurement(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) if (const auto* value = hash.find(key)) checksum += *value;
        });
        const auto tree_lookup = repeat_measurement(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) if (const auto* value = tree.find(key)) checksum += *value;
        });
        const auto sorted_lookup = repeat_measurement(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) if (const auto* value = sorted.find(key)) checksum += *value;
        });
        const auto trie_lookup = repeat_measurement(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) if (const auto* value = trie.find(string_keys[key % string_keys.size()])) checksum += *value;
        });

        const auto tree_range = repeat_measurement(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) {
                const auto high = std::min<std::uint64_t>(key + 8, options.n - 1);
                checksum += tree.range(key, high).size();
            }
        });
        const auto sorted_range = repeat_measurement(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) {
                const auto high = std::min<std::uint64_t>(key + 8, options.n - 1);
                checksum += sorted.range(key, high).size();
            }
        });
        const auto bitmap_filter = repeat_measurement(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) checksum += bitmap.filter(key % 128).size();
        });
        const auto trie_prefix = repeat_measurement(options, options.operations, [&](std::size_t, bool) {
            for (const auto key : queries) {
                const auto& value = string_keys[key % string_keys.size()];
                checksum += trie.prefix_search(value.substr(0, std::min<std::size_t>(6, value.size())), 16).size();
            }
        });

        const auto hash_update = repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
            for (const auto key : queries) hash.insert_or_assign(key, key * 3 + repetition);
            checksum += hash.size();
        });
        const auto tree_update = repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
            for (const auto key : queries) tree.insert_or_assign(key, key * 3 + repetition);
            checksum += tree.size();
        });
        const auto sorted_update = repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
            for (const auto key : queries) sorted.insert_or_assign(key, key * 3 + repetition);
            checksum += sorted.size();
        });

        std::cout << std::fixed << std::setprecision(3);
        std::cout << "{\n"
                  << "  \"profile_id\": \"local-" << options.seed << '-' << options.n << '-' << options.operations << "\",\n"
                  << "  \"schema_version\": 2,\n"
                  << "  \"evidence_state\": \"MEASURED_LOCAL_PROCESS_REPEATED\",\n"
                  << "  \"protocol\": \"morpheus-calibration-v2\",\n"
                  << "  \"n\": " << options.n << ",\n"
                  << "  \"operations\": " << options.operations << ",\n"
                  << "  \"seed\": " << options.seed << ",\n"
                  << "  \"repetitions\": " << options.repetitions << ",\n"
                  << "  \"warmup_repetitions\": " << options.warmup << ",\n"
                  << "  \"checksum\": " << checksum << ",\n"
                  << "  \"machine\": {\"compiler\":\"" << json_escape(__VERSION__)
                  << "\",\"cplusplus\":\"" << __cplusplus << "\"},\n"
                  << "  \"measurements\": [\n";

        const std::vector<std::tuple<std::string_view, std::string_view, const Stats*>> measurements = {
            {"robin_hood_hash", "build", &hash_build},
            {"ordered_tree", "build", &tree_build},
            {"sorted_array", "build", &sorted_build},
            {"bitmap", "build", &bitmap_build},
            {"radix_trie", "build", &trie_build},
            {"robin_hood_hash", "point_lookup", &hash_lookup},
            {"ordered_tree", "point_lookup", &tree_lookup},
            {"sorted_array", "point_lookup", &sorted_lookup},
            {"radix_trie", "point_lookup", &trie_lookup},
            {"ordered_tree", "range_scan", &tree_range},
            {"sorted_array", "range_scan", &sorted_range},
            {"bitmap", "filter", &bitmap_filter},
            {"radix_trie", "prefix_search", &trie_prefix},
            {"robin_hood_hash", "update", &hash_update},
            {"ordered_tree", "update", &tree_update},
            {"sorted_array", "update", &sorted_update},
        };

        for (std::size_t i = 0; i < measurements.size(); ++i) {
            const auto& [primitive, operation, stats] = measurements[i];
            print_measurement(primitive, operation, *stats, options.repetitions);
            std::cout << (i + 1 == measurements.size() ? "\n" : ",\n");
        }
        std::cout << "  ]\n}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "morpheus_calibrate: " << error.what() << '\n';
        return 2;
    }
}
