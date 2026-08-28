#include "morpheus/migration.hpp"
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
    struct Record {
        std::uint64_t id{};
        std::uint64_t value{};
        bool operator==(const Record&) const = default;
    };

    void insert(const Record& record) { records_.push_back(record); }
    [[nodiscard]] const std::vector<Record>& records() const noexcept { return records_; }

private:
    std::vector<Record> records_;
};

static_assert(morpheus::SnapshotMigratableIndex<Payload>);

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

std::shared_ptr<Payload> make_payload(std::size_t values) {
    auto payload = std::make_shared<Payload>();
    for (std::size_t i = 0; i < values; ++i) {
        payload->insert({static_cast<std::uint64_t>(i), static_cast<std::uint64_t>(i * 17U + 3U)});
    }
    return payload;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const auto options = parse_args(argc, argv);
        using Slot = morpheus::VersionedSlot<Payload>;
        using Clock = std::chrono::steady_clock;

        std::cout << "repetition,readers,transitions,payload_values,snapshot_capture_ns_per,shadow_rebuild_ns_per,activate_ns_per,rollback_ns_per,reads,invalid_reads\n";

        for (std::size_t repetition = 0; repetition < options.repetitions; ++repetition) {
            auto payload_a = make_payload(options.payload_values);
            Slot slot("candidate-a", std::shared_ptr<const Payload>(payload_a));

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
                        const bool known_candidate =
                            lease->candidate_id == "candidate-a" || lease->candidate_id == "candidate-b";
                        const auto& records = lease->payload->records();
                        const bool complete_snapshot =
                            records.size() == options.payload_values
                            && (!records.empty() && records.front().id == 0)
                            && records.back().id == options.payload_values - 1;
                        if (!known_candidate || !complete_snapshot) invalid.fetch_add(1, std::memory_order_relaxed);
                        reads.fetch_add(1, std::memory_order_relaxed);
                    }
                });
            }

            std::uint64_t snapshot_capture_ns = 0;
            std::uint64_t shadow_rebuild_ns = 0;
            std::uint64_t activation_ns = 0;
            std::uint64_t rollback_ns = 0;

            for (std::size_t transition = 0; transition < options.transitions; ++transition) {
                const auto active_lease = slot.lease();

                const auto capture_start = Clock::now();
                const auto snapshot = morpheus::capture_index_snapshot(*active_lease->payload);
                const auto capture_end = Clock::now();
                snapshot_capture_ns += static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(capture_end - capture_start).count()
                );

                const auto rebuild_start = Clock::now();
                auto shadow = morpheus::rebuild_and_validate_index<Payload>(snapshot, [&](const Payload& candidate) {
                    return morpheus::snapshot_matches_index(snapshot, candidate);
                });
                const auto rebuild_end = Clock::now();
                shadow_rebuild_ns += static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(rebuild_end - rebuild_start).count()
                );

                const auto activate_start = Clock::now();
                (void)slot.activate_validated(
                    "candidate-a",
                    "candidate-b",
                    std::shared_ptr<const Payload>(shadow),
                    [&](const Payload& current, const Payload& staged) {
                        return current.records() == snapshot && staged.records() == snapshot;
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
                << (snapshot_capture_ns / options.transitions) << ','
                << (shadow_rebuild_ns / options.transitions) << ','
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
