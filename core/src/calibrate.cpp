#include "morpheus/structures.hpp"

#include <algorithm>
#include <chrono>
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

namespace {

struct Options {
    std::size_t n = 10000;
    std::size_t operations = 50000;
    std::uint64_t seed = 1337;
};

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string_view arg = argv[i];
        auto read_value = [&](std::size_t& target) {
            if (i + 1 >= argc) throw std::runtime_error("missing argument value");
            target = static_cast<std::size_t>(std::stoull(argv[++i]));
        };
        if (arg == "--n") {
            read_value(options.n);
        } else if (arg == "--ops") {
            read_value(options.operations);
        } else if (arg == "--seed") {
            if (i + 1 >= argc) throw std::runtime_error("missing seed value");
            options.seed = std::stoull(argv[++i]);
        } else {
            throw std::runtime_error("unknown option: " + std::string(arg));
        }
    }
    if (options.n == 0 || options.operations == 0) throw std::runtime_error("n and ops must be positive");
    return options;
}

template <typename Function>
double ns_per_operation(std::size_t operations, Function&& function) {
    const auto start = std::chrono::steady_clock::now();
    function();
    const auto stop = std::chrono::steady_clock::now();
    const auto elapsed = std::chrono::duration<double, std::nano>(stop - start).count();
    return elapsed / static_cast<double>(operations);
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

        morpheus::RobinHoodHashIndex<std::uint64_t, std::uint64_t> hash(options.n * 2);
        morpheus::OrderedTreeIndex<std::uint64_t, std::uint64_t> tree;
        morpheus::SortedArrayIndex<std::uint64_t, std::uint64_t> sorted;

        const auto hash_build_ns = ns_per_operation(options.n, [&] {
            for (const auto key : keys) hash.insert_or_assign(key, key * 2);
        });

        const auto tree_build_ns = ns_per_operation(options.n, [&] {
            for (const auto key : keys) tree.insert_or_assign(key, key * 2);
        });

        std::vector<std::pair<std::uint64_t, std::uint64_t>> rows;
        rows.reserve(options.n);
        for (const auto key : keys) rows.emplace_back(key, key * 2);
        const auto sorted_build_ns = ns_per_operation(options.n, [&] { sorted.bulk_load(rows); });

        std::uint64_t checksum = 0;
        const auto hash_lookup_ns = ns_per_operation(options.operations, [&] {
            for (const auto key : queries) {
                if (const auto* value = hash.find(key)) checksum = checksum + *value;
            }
        });
        const auto tree_lookup_ns = ns_per_operation(options.operations, [&] {
            for (const auto key : queries) {
                if (const auto* value = tree.find(key)) checksum = checksum + *value;
            }
        });
        const auto sorted_lookup_ns = ns_per_operation(options.operations, [&] {
            for (const auto key : queries) {
                if (const auto* value = sorted.find(key)) checksum = checksum + *value;
            }
        });

        std::cout << std::fixed << std::setprecision(3);
        std::cout << "{\n"
                  << "  \"schema_version\": 1,\n"
                  << "  \"evidence_state\": \"MEASURED_LOCAL_PROCESS\",\n"
                  << "  \"protocol\": \"morpheus-calibration-smoke-v1\",\n"
                  << "  \"n\": " << options.n << ",\n"
                  << "  \"operations\": " << options.operations << ",\n"
                  << "  \"seed\": " << options.seed << ",\n"
                  << "  \"checksum\": " << checksum << ",\n"
                  << "  \"measurements\": [\n"
                  << "    {\"primitive\":\"robin_hood_hash\",\"operation\":\"build\",\"ns_per_op\":" << hash_build_ns << "},\n"
                  << "    {\"primitive\":\"ordered_tree\",\"operation\":\"build\",\"ns_per_op\":" << tree_build_ns << "},\n"
                  << "    {\"primitive\":\"sorted_array\",\"operation\":\"build\",\"ns_per_op\":" << sorted_build_ns << "},\n"
                  << "    {\"primitive\":\"robin_hood_hash\",\"operation\":\"point_lookup\",\"ns_per_op\":" << hash_lookup_ns << "},\n"
                  << "    {\"primitive\":\"ordered_tree\",\"operation\":\"point_lookup\",\"ns_per_op\":" << tree_lookup_ns << "},\n"
                  << "    {\"primitive\":\"sorted_array\",\"operation\":\"point_lookup\",\"ns_per_op\":" << sorted_lookup_ns << "}\n"
                  << "  ]\n"
                  << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "morpheus_calibrate: " << error.what() << '\n';
        return 2;
    }
}
