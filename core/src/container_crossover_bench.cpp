#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
constexpr std::size_t kUniverse = 65536;
constexpr std::size_t kDenseWords = kUniverse / 64;

struct Options {
    std::size_t cardinality = 4096;
    std::size_t repetitions = 200;
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
        if (key != "--cardinality" && key != "--repetitions" && key != "--seed") {
            throw std::invalid_argument("unknown option: " + std::string(key));
        }
        if (i + 1 >= argc) throw std::invalid_argument("missing value for " + std::string(key));
        const auto value = parse_size(argv[++i], key);
        if (key == "--cardinality") options.cardinality = value;
        else if (key == "--repetitions") options.repetitions = value;
        else if (value > static_cast<std::size_t>(UINT32_MAX)) throw std::invalid_argument("--seed exceeds uint32 range");
        else options.seed = static_cast<std::uint32_t>(value);
    }
    if (options.cardinality < 1 || options.cardinality > kUniverse) {
        throw std::invalid_argument("--cardinality must be in [1, 65536]");
    }
    if (options.repetitions < 1) throw std::invalid_argument("--repetitions must be positive");
    return options;
}

std::vector<std::uint16_t> make_values(std::size_t cardinality, std::uint32_t seed) {
    std::vector<std::uint32_t> universe(kUniverse);
    for (std::uint32_t i = 0; i < universe.size(); ++i) universe[i] = i;
    std::mt19937 rng(seed);
    std::shuffle(universe.begin(), universe.end(), rng);

    std::vector<std::uint16_t> values;
    values.reserve(cardinality);
    for (std::size_t i = 0; i < cardinality; ++i) values.push_back(static_cast<std::uint16_t>(universe[i]));
    std::sort(values.begin(), values.end());
    return values;
}

class SparseContainer {
public:
    explicit SparseContainer(std::vector<std::uint16_t> values) : values_(std::move(values)) {}

    [[nodiscard]] bool contains(std::uint16_t value) const noexcept {
        return std::binary_search(values_.begin(), values_.end(), value);
    }

    [[nodiscard]] std::size_t intersection_size(const SparseContainer& other) const {
        std::size_t count = 0;
        auto left = values_.begin();
        auto right = other.values_.begin();
        while (left != values_.end() && right != other.values_.end()) {
            if (*left < *right) ++left;
            else if (*right < *left) ++right;
            else {
                ++count;
                ++left;
                ++right;
            }
        }
        return count;
    }

    [[nodiscard]] std::size_t union_size(const SparseContainer& other) const {
        std::size_t count = 0;
        auto left = values_.begin();
        auto right = other.values_.begin();
        while (left != values_.end() && right != other.values_.end()) {
            if (*left < *right) {
                ++count;
                ++left;
            } else if (*right < *left) {
                ++count;
                ++right;
            } else {
                ++count;
                ++left;
                ++right;
            }
        }
        return count + static_cast<std::size_t>(std::distance(left, values_.end()))
                     + static_cast<std::size_t>(std::distance(right, other.values_.end()));
    }

    [[nodiscard]] std::vector<std::uint16_t> materialize() const { return values_; }

private:
    std::vector<std::uint16_t> values_;
};

class DenseContainer {
public:
    explicit DenseContainer(const std::vector<std::uint16_t>& values) {
        words_.fill(0);
        for (const auto value : values) {
            words_[static_cast<std::size_t>(value) >> 6U] |= std::uint64_t{1} << (value & 63U);
        }
    }

    [[nodiscard]] bool contains(std::uint16_t value) const noexcept {
        const auto word = static_cast<std::size_t>(value) >> 6U;
        const auto mask = std::uint64_t{1} << (value & 63U);
        return (words_[word] & mask) != 0;
    }

    [[nodiscard]] std::size_t intersection_size(const DenseContainer& other) const noexcept {
        std::size_t count = 0;
        for (std::size_t i = 0; i < words_.size(); ++i) {
            count += static_cast<std::size_t>(std::popcount(words_[i] & other.words_[i]));
        }
        return count;
    }

    [[nodiscard]] std::size_t union_size(const DenseContainer& other) const noexcept {
        std::size_t count = 0;
        for (std::size_t i = 0; i < words_.size(); ++i) {
            count += static_cast<std::size_t>(std::popcount(words_[i] | other.words_[i]));
        }
        return count;
    }

    [[nodiscard]] std::vector<std::uint16_t> materialize() const {
        std::vector<std::uint16_t> out;
        for (std::size_t word_index = 0; word_index < words_.size(); ++word_index) {
            auto bits = words_[word_index];
            while (bits != 0) {
                const auto bit = static_cast<unsigned>(std::countr_zero(bits));
                out.push_back(static_cast<std::uint16_t>((word_index << 6U) + bit));
                bits &= bits - 1;
            }
        }
        return out;
    }

private:
    std::array<std::uint64_t, kDenseWords> words_{};
};

template <typename Operation>
double benchmark_ns_per_op(std::size_t repetitions, Operation&& operation, std::size_t& sink) {
    const auto start = Clock::now();
    for (std::size_t i = 0; i < repetitions; ++i) sink ^= operation(i);
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count();
    return static_cast<double>(elapsed) / static_cast<double>(repetitions);
}

struct Measurements {
    double intersection_ns = 0;
    double union_ns = 0;
    double contains_ns = 0;
    double materialize_ns = 0;
    std::size_t intersection_size = 0;
    std::size_t union_size = 0;
};

template <typename Container>
Measurements measure(const Container& left, const Container& right, const Options& options, std::size_t& sink) {
    Measurements result;
    result.intersection_ns = benchmark_ns_per_op(options.repetitions, [&](std::size_t) {
        result.intersection_size = left.intersection_size(right);
        return result.intersection_size;
    }, sink);
    result.union_ns = benchmark_ns_per_op(options.repetitions, [&](std::size_t) {
        result.union_size = left.union_size(right);
        return result.union_size;
    }, sink);
    result.contains_ns = benchmark_ns_per_op(options.repetitions * 64U, [&](std::size_t i) {
        return left.contains(static_cast<std::uint16_t>((i * 104729U) & 0xFFFFU)) ? std::size_t{1} : std::size_t{0};
    }, sink);
    result.materialize_ns = benchmark_ns_per_op(options.repetitions, [&](std::size_t) {
        return left.materialize().size();
    }, sink);
    return result;
}

void print_csv_row(std::string_view representation, std::string_view operation, const Options& options,
                   double ns_per_op, std::size_t result_size) {
    std::cout << representation << ',' << operation << ',' << options.cardinality << ',' << options.repetitions
              << ',' << options.seed << ',' << std::fixed << std::setprecision(1) << ns_per_op << ',' << result_size << '\n';
}

void print_human_row(std::string_view representation, std::string_view operation, double ns_per_op,
                     std::size_t result_size) {
    std::cout << std::left << std::setw(9) << representation << std::setw(16) << operation
              << std::right << std::setw(14) << std::fixed << std::setprecision(1) << ns_per_op
              << std::setw(16) << result_size << '\n';
}

int run(const Options& options) {
    const auto left_values = make_values(options.cardinality, options.seed);
    const auto right_values = make_values(options.cardinality, options.seed + 1U);
    const SparseContainer sparse_left(left_values);
    const SparseContainer sparse_right(right_values);
    const DenseContainer dense_left(left_values);
    const DenseContainer dense_right(right_values);

    std::size_t sink = 0;
    const auto sparse = measure(sparse_left, sparse_right, options, sink);
    const auto dense = measure(dense_left, dense_right, options, sink);

    if (sparse.intersection_size != dense.intersection_size || sparse.union_size != dense.union_size) {
        throw std::runtime_error("sparse/dense benchmark representations disagree on result cardinality");
    }

    if (options.csv) {
        std::cout << "representation,operation,cardinality,repetitions,seed,ns_per_op,result_size\n";
        print_csv_row("sparse", "intersection", options, sparse.intersection_ns, sparse.intersection_size);
        print_csv_row("dense", "intersection", options, dense.intersection_ns, dense.intersection_size);
        print_csv_row("sparse", "union", options, sparse.union_ns, sparse.union_size);
        print_csv_row("dense", "union", options, dense.union_ns, dense.union_size);
        print_csv_row("sparse", "contains", options, sparse.contains_ns, options.cardinality);
        print_csv_row("dense", "contains", options, dense.contains_ns, options.cardinality);
        print_csv_row("sparse", "materialize", options, sparse.materialize_ns, options.cardinality);
        print_csv_row("dense", "materialize", options, dense.materialize_ns, options.cardinality);
    } else {
        std::cout << "MORPHEUS sparse-vs-dense container crossover benchmark\n"
                  << "cardinality=" << options.cardinality << " repetitions=" << options.repetitions << '\n'
                  << std::left << std::setw(9) << "repr" << std::setw(16) << "operation"
                  << std::right << std::setw(14) << "ns/op" << std::setw(16) << "result size" << '\n';
        print_human_row("sparse", "intersection", sparse.intersection_ns, sparse.intersection_size);
        print_human_row("dense", "intersection", dense.intersection_ns, dense.intersection_size);
        print_human_row("sparse", "union", sparse.union_ns, sparse.union_size);
        print_human_row("dense", "union", dense.union_ns, dense.union_size);
        print_human_row("sparse", "contains", sparse.contains_ns, options.cardinality);
        print_human_row("dense", "contains", dense.contains_ns, options.cardinality);
        print_human_row("sparse", "materialize", sparse.materialize_ns, options.cardinality);
        print_human_row("dense", "materialize", dense.materialize_ns, options.cardinality);
    }

    if (sink == static_cast<std::size_t>(-1)) std::cerr << "benchmark sink=" << sink << '\n';
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
