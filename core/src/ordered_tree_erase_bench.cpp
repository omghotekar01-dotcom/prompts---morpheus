#include "morpheus/structures.hpp"

#include <algorithm>
#include <charconv>
#include <chrono>
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
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
using Tree = morpheus::OrderedTreeIndex<std::uint32_t, std::uint32_t>;
using Baseline = std::map<std::uint32_t, std::uint32_t>;

struct Options {
    std::size_t size = 4096;
    std::size_t erase_count = 64;
    std::size_t repetitions = 3;
    std::uint32_t seed = 1337;
    bool csv = false;
};

std::size_t parse_size(std::string_view value, std::string_view option) {
    std::size_t parsed = 0;
    const auto* begin = value.data();
    const auto* end = begin + value.size();
    const auto [ptr, error] = std::from_chars(begin, end, parsed);
    if (error != std::errc{} || ptr != end) {
        throw std::invalid_argument(std::string(option) + " requires a non-negative integer");
    }
    return parsed;
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string_view key{argv[i]};
        if (key == "--csv") {
            options.csv = true;
            continue;
        }
        if (key != "--size" && key != "--erase-count" && key != "--repetitions" && key != "--seed") {
            throw std::invalid_argument("unknown option: " + std::string(key));
        }
        if (i + 1 >= argc) throw std::invalid_argument("missing value for " + std::string(key));
        const auto value = parse_size(argv[++i], key);
        if (key == "--size") options.size = value;
        else if (key == "--erase-count") options.erase_count = value;
        else if (key == "--repetitions") options.repetitions = value;
        else if (value > static_cast<std::size_t>(UINT32_MAX)) throw std::invalid_argument("--seed exceeds uint32 range");
        else options.seed = static_cast<std::uint32_t>(value);
    }
    if (options.size < 2 || options.size > static_cast<std::size_t>(UINT32_MAX)) {
        throw std::invalid_argument("--size must be in [2, UINT32_MAX]");
    }
    if (options.erase_count < 1 || options.erase_count >= options.size) {
        throw std::invalid_argument("--erase-count must be in [1, size-1]");
    }
    if (options.repetitions < 1) throw std::invalid_argument("--repetitions must be positive");
    return options;
}

std::vector<std::uint32_t> make_keys(std::size_t count, std::uint32_t seed) {
    std::vector<std::uint32_t> keys(count);
    std::iota(keys.begin(), keys.end(), std::uint32_t{0});
    std::mt19937 rng(seed);
    std::shuffle(keys.begin(), keys.end(), rng);
    return keys;
}

Tree build_tree(const std::vector<std::uint32_t>& keys) {
    Tree tree;
    for (const auto key : keys) tree.insert_or_assign(key, key ^ 0xA5A5A5A5U);
    if (!tree.validate() || tree.size() != keys.size()) throw std::runtime_error("OrderedTreeIndex failed pre-benchmark validation");
    return tree;
}

Baseline build_baseline(const std::vector<std::uint32_t>& keys) {
    Baseline tree;
    for (const auto key : keys) tree.insert_or_assign(key, key ^ 0xA5A5A5A5U);
    return tree;
}

struct Measurement {
    double ns_per_erase = 0.0;
    std::size_t final_size = 0;
    std::size_t checksum = 0;
};

Measurement measure_ordered_tree(const std::vector<std::uint32_t>& insertion_order,
                                 const std::vector<std::uint32_t>& erase_order,
                                 std::size_t repetitions) {
    std::uint64_t total_ns = 0;
    std::size_t checksum = 0;
    std::size_t final_size = 0;
    for (std::size_t repetition = 0; repetition < repetitions; ++repetition) {
        auto tree = build_tree(insertion_order);
        const auto start = Clock::now();
        for (const auto key : erase_order) {
            if (!tree.erase(key)) throw std::runtime_error("OrderedTreeIndex erase unexpectedly failed");
        }
        total_ns += static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count()
        );
        if (!tree.validate()) throw std::runtime_error("OrderedTreeIndex failed post-erase validation");
        final_size = tree.size();
        for (const auto& [key, value] : tree.items()) checksum ^= static_cast<std::size_t>(key) + static_cast<std::size_t>(value);
    }
    return {
        static_cast<double>(total_ns) / static_cast<double>(repetitions * erase_order.size()),
        final_size,
        checksum,
    };
}

Measurement measure_std_map(const std::vector<std::uint32_t>& insertion_order,
                            const std::vector<std::uint32_t>& erase_order,
                            std::size_t repetitions) {
    std::uint64_t total_ns = 0;
    std::size_t checksum = 0;
    std::size_t final_size = 0;
    for (std::size_t repetition = 0; repetition < repetitions; ++repetition) {
        auto tree = build_baseline(insertion_order);
        const auto start = Clock::now();
        for (const auto key : erase_order) {
            if (tree.erase(key) != 1U) throw std::runtime_error("std::map erase unexpectedly failed");
        }
        total_ns += static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count()
        );
        final_size = tree.size();
        for (const auto& [key, value] : tree) checksum ^= static_cast<std::size_t>(key) + static_cast<std::size_t>(value);
    }
    return {
        static_cast<double>(total_ns) / static_cast<double>(repetitions * erase_order.size()),
        final_size,
        checksum,
    };
}

void print_csv(std::string_view implementation, const Options& options, const Measurement& measurement) {
    std::cout << implementation << ',' << options.size << ',' << options.erase_count << ',' << options.repetitions
              << ',' << options.seed << ',' << std::fixed << std::setprecision(1) << measurement.ns_per_erase
              << ',' << measurement.final_size << ',' << measurement.checksum << '\n';
}

void print_human(std::string_view implementation, const Measurement& measurement) {
    std::cout << std::left << std::setw(20) << implementation
              << std::right << std::setw(16) << std::fixed << std::setprecision(1) << measurement.ns_per_erase
              << std::setw(14) << measurement.final_size << '\n';
}

int run(const Options& options) {
    const auto insertion_order = make_keys(options.size, options.seed);
    auto erase_order = make_keys(options.size, options.seed ^ 0x9E3779B9U);
    erase_order.resize(options.erase_count);

    const auto ordered = measure_ordered_tree(insertion_order, erase_order, options.repetitions);
    const auto baseline = measure_std_map(insertion_order, erase_order, options.repetitions);
    const auto expected_size = options.size - options.erase_count;
    if (ordered.final_size != expected_size || baseline.final_size != expected_size) {
        throw std::runtime_error("erase benchmark final-size mismatch");
    }

    if (options.csv) {
        std::cout << "implementation,size,erase_count,repetitions,seed,ns_per_erase,final_size,checksum\n";
        print_csv("ordered_tree_rebuild", options, ordered);
        print_csv("std_map", options, baseline);
    } else {
        std::cout << "MORPHEUS OrderedTreeIndex erase baseline benchmark\n"
                  << "size=" << options.size << " erase_count=" << options.erase_count
                  << " repetitions=" << options.repetitions << '\n'
                  << std::left << std::setw(20) << "implementation"
                  << std::right << std::setw(16) << "ns/erase" << std::setw(14) << "final size" << '\n';
        print_human("ordered_tree_rebuild", ordered);
        print_human("std_map", baseline);
    }
    return 0;
}

} // namespace

int main(int argc, char** argv) {
    try {
        return run(parse_options(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 2;
    }
}
