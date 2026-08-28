#include "morpheus/compressed_bitmap.hpp"

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <random>
#include <string_view>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
using Bitmap = morpheus::CompressedBitmap<std::uint32_t>;

struct Options {
    std::size_t cardinality = 4096;
    std::size_t repetitions = 200;
    std::uint32_t seed = 1337;
    bool csv = false;
};

std::size_t parse_size(const char* value) {
    return static_cast<std::size_t>(std::strtoull(value, nullptr, 10));
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string_view key{argv[i]};
        if (key == "--csv") {
            options.csv = true;
            continue;
        }
        if (i + 1 >= argc) break;
        if (key == "--cardinality") options.cardinality = parse_size(argv[++i]);
        else if (key == "--repetitions") options.repetitions = parse_size(argv[++i]);
        else if (key == "--seed") options.seed = static_cast<std::uint32_t>(parse_size(argv[++i]));
    }
    options.cardinality = std::clamp<std::size_t>(options.cardinality, 1, 65536);
    options.repetitions = std::max<std::size_t>(options.repetitions, 1);
    return options;
}

Bitmap make_bitmap(std::size_t cardinality, std::uint32_t seed) {
    std::vector<std::uint32_t> universe(65536);
    for (std::uint32_t i = 0; i < universe.size(); ++i) universe[i] = i;
    std::mt19937 rng(seed);
    std::shuffle(universe.begin(), universe.end(), rng);

    Bitmap bitmap;
    for (std::size_t i = 0; i < cardinality; ++i) bitmap.add(universe[i]);
    return bitmap;
}

template <typename Operation>
double benchmark_ns_per_op(std::size_t repetitions, Operation&& operation, std::size_t& sink) {
    const auto start = Clock::now();
    for (std::size_t i = 0; i < repetitions; ++i) sink ^= operation(i);
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count();
    return static_cast<double>(elapsed) / static_cast<double>(repetitions);
}

void print_row(std::string_view operation, double ns_per_op, std::size_t result_cardinality) {
    std::cout << std::left << std::setw(18) << operation
              << std::right << std::setw(14) << std::fixed << std::setprecision(1) << ns_per_op
              << std::setw(16) << result_cardinality << '\n';
}

void print_csv_row(std::string_view operation, const Options& options, std::size_t dense_containers,
                   double ns_per_op, std::size_t result_cardinality) {
    std::cout << operation << ',' << options.cardinality << ',' << options.repetitions << ','
              << options.seed << ',' << dense_containers << ',' << std::fixed << std::setprecision(1)
              << ns_per_op << ',' << result_cardinality << '\n';
}

} // namespace

int main(int argc, char** argv) {
    const auto options = parse_options(argc, argv);
    const auto left = make_bitmap(options.cardinality, options.seed);
    const auto right = make_bitmap(options.cardinality, options.seed + 1U);

    std::size_t sink = 0;
    std::size_t intersection_cardinality = 0;
    std::size_t union_cardinality = 0;

    const auto intersection_ns = benchmark_ns_per_op(options.repetitions, [&](std::size_t) {
        const auto result = left.intersection(right);
        intersection_cardinality = result.size();
        return result.size();
    }, sink);

    const auto union_ns = benchmark_ns_per_op(options.repetitions, [&](std::size_t) {
        const auto result = left.set_union(right);
        union_cardinality = result.size();
        return result.size();
    }, sink);

    const auto contains_ns = benchmark_ns_per_op(options.repetitions * 64U, [&](std::size_t i) {
        return left.contains(static_cast<std::uint32_t>((i * 104729U) & 0xFFFFU)) ? std::size_t{1} : std::size_t{0};
    }, sink);

    const auto values_ns = benchmark_ns_per_op(options.repetitions, [&](std::size_t) {
        return left.values().size();
    }, sink);

    const auto dense_containers = left.dense_container_count();
    if (options.csv) {
        std::cout << "operation,cardinality,repetitions,seed,dense_containers,ns_per_op,result_size\n";
        print_csv_row("intersection", options, dense_containers, intersection_ns, intersection_cardinality);
        print_csv_row("union", options, dense_containers, union_ns, union_cardinality);
        print_csv_row("contains", options, dense_containers, contains_ns, left.size());
        print_csv_row("materialize", options, dense_containers, values_ns, left.size());
    } else {
        std::cout << "MORPHEUS adaptive bitmap microbenchmark\n"
                  << "cardinality=" << options.cardinality
                  << " repetitions=" << options.repetitions
                  << " dense_containers=" << dense_containers << '\n'
                  << std::left << std::setw(18) << "operation"
                  << std::right << std::setw(14) << "ns/op"
                  << std::setw(16) << "result size" << '\n';

        print_row("intersection", intersection_ns, intersection_cardinality);
        print_row("union", union_ns, union_cardinality);
        print_row("contains", contains_ns, left.size());
        print_row("materialize", values_ns, left.size());
    }

    if (sink == static_cast<std::size_t>(-1)) std::cerr << "benchmark sink=" << sink << '\n';
    return 0;
}
