#include "morpheus/versioned_slot.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

struct Payload {
    std::uint64_t marker{};
    std::vector<std::uint64_t> values;
};

struct Options {
    std::size_t readers = 4;
    std::size_t transitions = 100;
    std::size_t repetitions = 3;
    std::size_t payload_values = 1024;
};

std::size_t parse_size(const char* text, const char* name) {
    try {
        const auto value = std::stoull(text);
        if (value == 0) throw std::invalid_argument("zero");
        return static_cast<std::size_t>(value);
    } catch (...) {
        throw std::invalid_argument(std::string("invalid value for ") + name);
    }
}

Options parse_args(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto require_value = [&](const char* name) -> const char* {
            if (i + 1 >= argc) throw std::invalid_argument(std::string("missing value for ") + name);
            return argv[++i];
        };

        if (arg == "--readers") options.readers = parse_size(require_value("--readers"), "--readers");
        else if (arg == "--transitions") options.transitions = parse_size(require_value("--transitions"), "--transitions");
        else if (arg == "--repetitions") options.repetitions = parse_size(require_value("--repetitions"), "--repetitions");
        else if (arg == "--payload-values") options.payload_values = parse_size(require_value("--payload-values"), "--payload-values");
        else if (arg == "--help" || arg == "-h") {
            std::cout << "usage: morpheus_versioned_slot_bench [--readers N] [--transitions N] "
                         "[--repetitions N] [--payload-values N]\n";
            std::exit(0);
        } else {
            throw std::invalid_argument("unknown argument: " + arg);
        }
    }
    return options;
}

std::shared_ptr<const Payload> make_payload(std::uint64_t marker, std::size_t values) {
    auto payload = std::make_shared<Payload>();
    payload->marker = marker;
    payload->values.resize(values);
    for (std::size_t i = 0; i < values; ++i) payload->values[i] = marker + static_cast<std::uint64_t>(i);
    return payload;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const auto options = parse_args(argc, argv);
        using Slot = morpheus::VersionedSlot<Payload>;
        using Clock = std::chrono::steady_clock;

        std::cout << "repetition,readers,transitions,payload_values,activate_ns_per,rollback_ns_per,reads,invalid_reads\n";

        for (std::size_t repetition = 0; repetition < options.repetitions; ++repetition) {
            auto payload_a = make_payload(1, options.payload_values);
            auto payload_b = make_payload(2, options.payload_values);
            Slot slot("candidate-a", payload_a);

            std::atomic<bool> stop{false};
            std::atomic<std::uint64_t> reads{0};
            std::atomic<std::uint64_t> invalid{0};
            std::vector<std::thread> readers;
            readers.reserve(options.readers);

            for (std::size_t reader = 0; reader < options.readers; ++reader) {
                readers.emplace_back([&] {
                    while (!stop.load(std::memory_order_relaxed)) {
                        auto lease = slot.lease();
                        if (!lease || !lease->payload) {
                            invalid.fetch_add(1, std::memory_order_relaxed);
                            continue;
                        }
                        const bool valid_a = lease->candidate_id == "candidate-a" && lease->payload->marker == 1;
                        const bool valid_b = lease->candidate_id == "candidate-b" && lease->payload->marker == 2;
                        if (!valid_a && !valid_b) invalid.fetch_add(1, std::memory_order_relaxed);
                        reads.fetch_add(1, std::memory_order_relaxed);
                    }
                });
            }

            std::uint64_t activation_ns = 0;
            std::uint64_t rollback_ns = 0;
            for (std::size_t transition = 0; transition < options.transitions; ++transition) {
                const auto activate_start = Clock::now();
                (void)slot.activate_validated(
                    "candidate-a",
                    "candidate-b",
                    payload_b,
                    [](const Payload& current, const Payload& staged) {
                        return staged.marker == current.marker + 1 && staged.values.size() == current.values.size();
                    }
                );
                const auto activate_end = Clock::now();
                activation_ns += static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(activate_end - activate_start).count()
                );

                const auto rollback_start = Clock::now();
                (void)slot.rollback("candidate-b");
                const auto rollback_end = Clock::now();
                rollback_ns += static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(rollback_end - rollback_start).count()
                );
            }

            stop.store(true, std::memory_order_relaxed);
            for (auto& reader : readers) reader.join();

            const auto invalid_reads = invalid.load(std::memory_order_relaxed);
            if (invalid_reads != 0) {
                std::cerr << "versioned-slot benchmark observed invalid reader state: " << invalid_reads << "\n";
                return 2;
            }

            std::cout
                << repetition << ','
                << options.readers << ','
                << options.transitions << ','
                << options.payload_values << ','
                << (activation_ns / options.transitions) << ','
                << (rollback_ns / options.transitions) << ','
                << reads.load(std::memory_order_relaxed) << ','
                << invalid_reads << '\n';
        }

        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
