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

struct MeasurementDescriptor {
    std::string_view primitive;
    std::string_view implementation_id;
    std::string_view operation;
    const Stats* stats;
};

constexpr std::string_view HASH_IMPL = "morpheus.RobinHoodHashIndex.v1";
constexpr std::string_view TREE_IMPL = "morpheus.BPlusTreeIndex.rebalanced.v1";
constexpr std::string_view SORTED_IMPL = "morpheus.MutableSortedArrayIndex.v1";
constexpr std::string_view TRIE_IMPL = "morpheus.MutableMultiPrefixTrie.v1";
constexpr std::string_view BITMAP_IMPL = "morpheus.CompressedBitmapFilterIndex.adaptive32.v1";

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string_view arg = argv[i];
        auto read_size = [&](std::size_t& target) {
            if (i + 1 >= argc) throw std::runtime_error("missing argument value");
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
    if (options.n > static_cast<std::size_t>(std::numeric_limits<std::uint32_t>::max())) {
        throw std::runtime_error("n exceeds 32-bit stable-slot calibration limit for compressed bitmap");
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
    return Stats{median, mean, std::sqrt(variance), sorted.front(), sorted.back(), std::move(samples)};
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

void print_measurement(const MeasurementDescriptor& descriptor, std::size_t repetitions) {
    const auto& stats = *descriptor.stats;
    std::cout << "    {\"primitive\":\"" << descriptor.primitive
              << "\",\"implementation_id\":\"" << descriptor.implementation_id
              << "\",\"operation\":\"" << descriptor.operation
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

        // Stable slot IDs follow insertion order, not logical key values. Keep
        // the inverse permutation so update benchmarks mutate the exact posting
        // that was inserted for each queried key. Using key%n here would measure
        // failed removes plus unrelated adds after shuffling, contaminating the
        // bitmap maintenance evidence.
        std::vector<std::uint32_t> slot_for_key(options.n);
        for (std::size_t i = 0; i < keys.size(); ++i) {
            slot_for_key[static_cast<std::size_t>(keys[i])] = static_cast<std::uint32_t>(i);
        }

        std::vector<std::uint64_t> queries(options.operations);
        std::uniform_int_distribution<std::size_t> distribution(0, options.n - 1);
        for (auto& query : queries) query = keys[distribution(rng)];

        std::vector<std::string> string_keys;
        string_keys.reserve(options.n);
        for (std::size_t i = 0; i < options.n; ++i) string_keys.push_back("key-" + std::to_string(i));

        std::uint64_t checksum = 0;

        const auto hash_build = repeat_measurement(options, options.n, [&](std::size_t repetition, bool) {
            morpheus::RobinHoodHashIndex<std::uint64_t, std::size_t> index(options.n * 2);
            for (std::size_t i = 0; i < keys.size(); ++i) index.insert_or_assign(keys[i], i + repetition);
            checksum += index.size();
        });
        const auto tree_build = repeat_measurement(options, options.n, [&](std::size_t repetition, bool) {
            morpheus::BPlusTreeIndex<std::uint64_t, std::size_t> index;
            for (std::size_t i = 0; i < keys.size(); ++i) index.insert_or_assign(keys[i], i + repetition);
            checksum += index.size();
        });
        const auto sorted_build = repeat_measurement(options, options.n, [&](std::size_t repetition, bool) {
            morpheus::MutableSortedArrayIndex<std::uint64_t, std::size_t> index;
            for (std::size_t i = 0; i < keys.size(); ++i) index.insert_or_assign(keys[i], i + repetition);
            checksum += index.size();
        });
        const auto bitmap_build = repeat_measurement(options, options.n, [&](std::size_t, bool) {
            morpheus::CompressedBitmapFilterIndex<std::uint64_t, std::uint32_t> index;
            for (std::size_t i = 0; i < keys.size(); ++i) index.add(keys[i] % 128, static_cast<std::uint32_t>(i));
            checksum += index.filter(0).size();
        });
        const auto trie_build = repeat_measurement(options, options.n, [&](std::size_t repetition, bool) {
            morpheus::MutableMultiPrefixTrie<std::size_t> index;
            for (std::size_t i = 0; i < string_keys.size(); ++i) index.add(string_keys[i], i + repetition);
            checksum += index.key_count();
        });

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
            for (const auto key : queries) hash.insert_or_assign(key, static_cast<std::size_t>(key + repetition));
            checksum += hash.size();
        });
        const auto tree_update = repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
            for (const auto key : queries) tree.insert_or_assign(key, static_cast<std::size_t>(key + repetition));
            checksum += tree.size();
        });
        const auto sorted_update = repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
            for (const auto key : queries) sorted.insert_or_assign(key, static_cast<std::size_t>(key + repetition));
            checksum += sorted.size();
        });
        const auto bitmap_update = repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
            for (const auto key : queries) {
                const auto slot = slot_for_key[static_cast<std::size_t>(key)];
                const auto old_category = key % 128;
                const auto new_category = (old_category + 1 + repetition) % 128;
                if (!bitmap.remove(old_category, slot)) {
                    throw std::runtime_error("bitmap calibration invariant: source posting missing");
                }
                bitmap.add(new_category, slot);
                if (!bitmap.remove(new_category, slot)) {
                    throw std::runtime_error("bitmap calibration invariant: temporary posting missing");
                }
                bitmap.add(old_category, slot);
            }
            checksum += bitmap.filter(0).size();
        });
        const auto trie_update = repeat_measurement(options, options.operations, [&](std::size_t repetition, bool) {
            for (const auto key : queries) {
                const auto index = static_cast<std::size_t>(key % string_keys.size());
                trie.remove(string_keys[index], index);
                trie.add(string_keys[index], index + repetition + options.n);
                trie.remove(string_keys[index], index + repetition + options.n);
                trie.add(string_keys[index], index);
            }
            checksum += trie.key_count();
        });

        std::cout << std::fixed << std::setprecision(3);
        std::cout << "{\n"
                  << "  \"profile_id\": \"local-" << options.seed << '-' << options.n << '-' << options.operations << "\",\n"
                  << "  \"schema_version\": 3,\n"
                  << "  \"evidence_state\": \"MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_BOUND\",\n"
                  << "  \"protocol\": \"morpheus-calibration-v3\",\n"
                  << "  \"truth_note\": \"Measurements are bound to explicit physical container implementation IDs. Stable-slot update workloads preserve the insertion mapping. Generated-wrapper auxiliary maintenance and end-to-end artifact behavior require separate measurement.\",\n"
                  << "  \"n\": " << options.n << ",\n"
                  << "  \"operations\": " << options.operations << ",\n"
                  << "  \"seed\": " << options.seed << ",\n"
                  << "  \"repetitions\": " << options.repetitions << ",\n"
                  << "  \"warmup_repetitions\": " << options.warmup << ",\n"
                  << "  \"checksum\": " << checksum << ",\n"
                  << "  \"machine\": {\"compiler\":\"" << json_escape(compiler_identity())
                  << "\",\"cplusplus\":\"" << __cplusplus << "\"},\n"
                  << "  \"measurements\": [\n";

        const std::vector<MeasurementDescriptor> measurements = {
            {"robin_hood_hash", HASH_IMPL, "build", &hash_build},
            {"ordered_tree", TREE_IMPL, "build", &tree_build},
            {"sorted_array", SORTED_IMPL, "build", &sorted_build},
            {"bitmap", BITMAP_IMPL, "build", &bitmap_build},
            {"radix_trie", TRIE_IMPL, "build", &trie_build},
            {"robin_hood_hash", HASH_IMPL, "point_lookup", &hash_lookup},
            {"ordered_tree", TREE_IMPL, "point_lookup", &tree_lookup},
            {"sorted_array", SORTED_IMPL, "point_lookup", &sorted_lookup},
            {"radix_trie", TRIE_IMPL, "point_lookup", &trie_lookup},
            {"ordered_tree", TREE_IMPL, "range_scan", &tree_range},
            {"sorted_array", SORTED_IMPL, "range_scan", &sorted_range},
            {"bitmap", BITMAP_IMPL, "filter", &bitmap_filter},
            {"radix_trie", TRIE_IMPL, "prefix_search", &trie_prefix},
            {"robin_hood_hash", HASH_IMPL, "update", &hash_update},
            {"ordered_tree", TREE_IMPL, "update", &tree_update},
            {"sorted_array", SORTED_IMPL, "update", &sorted_update},
            {"bitmap", BITMAP_IMPL, "update", &bitmap_update},
            {"radix_trie", TRIE_IMPL, "update", &trie_update},
        };

        for (std::size_t i = 0; i < measurements.size(); ++i) {
            print_measurement(measurements[i], options.repetitions);
            std::cout << (i + 1 == measurements.size() ? "\n" : ",\n");
        }
        std::cout << "  ]\n}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "morpheus_calibrate: " << error.what() << '\n';
        return 2;
    }
}
