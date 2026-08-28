#include "morpheus/migration_publish.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <typeindex>
#include <typeinfo>
#include <vector>

namespace {

struct SourceIndex {
    struct Record {
        std::uint64_t id{};
        std::uint64_t value{};
    };

    void insert(const Record& record) { rows_.push_back(record); }
    [[nodiscard]] const std::vector<Record>& records() const noexcept { return rows_; }

private:
    std::vector<Record> rows_;
};

struct TargetIndex {
    struct Record {
        std::uint64_t id{};
        std::uint64_t value{};
    };

    void insert(const Record& record) { rows_.push_back(record); }
    [[nodiscard]] const std::vector<Record>& records() const noexcept { return rows_; }

private:
    std::vector<Record> rows_;
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
            std::cout << "usage: morpheus_migration_publish_bench [--readers N] [--transitions N] "
                         "[--repetitions N] [--payload-values N]\n";
            std::exit(0);
        } else {
            throw std::invalid_argument("unknown argument: " + arg);
        }
    }
    return options;
}

std::shared_ptr<SourceIndex> make_source(std::size_t count) {
    auto source = std::make_shared<SourceIndex>();
    for (std::size_t i = 0; i < count; ++i) {
        source->insert(SourceIndex::Record{
            static_cast<std::uint64_t>(i),
            static_cast<std::uint64_t>(i * 31U + 7U),
        });
    }
    return source;
}

bool source_valid(const SourceIndex& source, std::size_t count) {
    const auto& rows = source.records();
    return rows.size() == count && !rows.empty() && rows.front().id == 0 &&
           rows.back().id == count - 1 && rows.back().value == (count - 1) * 31U + 7U;
}

bool target_valid(const TargetIndex& target, std::size_t count) {
    const auto& rows = target.records();
    return rows.size() == count && !rows.empty() && rows.front().id == 0 &&
           rows.back().id == count - 1 && rows.back().value == (count - 1) * 31U + 7U;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const auto options = parse_args(argc, argv);
        using Clock = std::chrono::steady_clock;

        std::cout << "repetition,readers,transitions,payload_values,migrate_validate_activate_ns_per,rollback_ns_per,reads,invalid_reads\n";

        for (std::size_t repetition = 0; repetition < options.repetitions; ++repetition) {
            const std::shared_ptr<const SourceIndex> source = make_source(options.payload_values);
            morpheus::ErasedVersionedSlot slot("source", source);

            std::atomic<bool> stop{false};
            std::atomic<std::uint64_t> reads{0};
            std::atomic<std::uint64_t> invalid{0};
            std::vector<std::thread> readers;
            readers.reserve(options.readers);

            for (std::size_t reader = 0; reader < options.readers; ++reader) {
                readers.emplace_back([&] {
                    while (!stop.load(std::memory_order_relaxed)) {
                        const auto version = slot.lease();
                        if (!version || !version->payload) {
                            invalid.fetch_add(1, std::memory_order_relaxed);
                            continue;
                        }
                        if (version->payload_type == std::type_index(typeid(SourceIndex))) {
                            const auto typed = std::shared_ptr<const SourceIndex>(
                                version->payload,
                                static_cast<const SourceIndex*>(version->payload.get())
                            );
                            if (version->candidate_id != "source" || !source_valid(*typed, options.payload_values)) {
                                invalid.fetch_add(1, std::memory_order_relaxed);
                            }
                        } else if (version->payload_type == std::type_index(typeid(TargetIndex))) {
                            const auto typed = std::shared_ptr<const TargetIndex>(
                                version->payload,
                                static_cast<const TargetIndex*>(version->payload.get())
                            );
                            if (version->candidate_id != "target" || !target_valid(*typed, options.payload_values)) {
                                invalid.fetch_add(1, std::memory_order_relaxed);
                            }
                        } else {
                            invalid.fetch_add(1, std::memory_order_relaxed);
                        }
                        reads.fetch_add(1, std::memory_order_relaxed);
                    }
                });
            }

            std::uint64_t migrate_ns = 0;
            std::uint64_t rollback_ns = 0;
            for (std::size_t transition = 0; transition < options.transitions; ++transition) {
                const auto source_version = slot.lease();
                if (source_version->candidate_id != "source") throw std::runtime_error("expected source generation");
                const auto active_source = std::shared_ptr<const SourceIndex>(
                    source_version->payload,
                    static_cast<const SourceIndex*>(source_version->payload.get())
                );

                const auto migrate_start = Clock::now();
                (void)morpheus::migrate_validate_and_activate<SourceIndex, TargetIndex>(
                    slot,
                    source_version,
                    "target",
                    *active_source,
                    [](const SourceIndex::Record& record) {
                        return TargetIndex::Record{record.id, record.value};
                    },
                    [&](const TargetIndex& candidate) {
                        return target_valid(candidate, options.payload_values);
                    }
                );
                const auto migrate_end = Clock::now();
                migrate_ns += static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(migrate_end - migrate_start).count()
                );

                const auto target_version = slot.lease();
                const auto rollback_start = Clock::now();
                (void)slot.rollback(target_version);
                const auto rollback_end = Clock::now();
                rollback_ns += static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(rollback_end - rollback_start).count()
                );
            }

            stop.store(true, std::memory_order_relaxed);
            for (auto& reader : readers) reader.join();

            const auto invalid_reads = invalid.load(std::memory_order_relaxed);
            if (invalid_reads != 0) {
                std::cerr << "cross-type migration benchmark observed invalid reader state: " << invalid_reads << '\n';
                return 2;
            }

            std::cout
                << repetition << ','
                << options.readers << ','
                << options.transitions << ','
                << options.payload_values << ','
                << (migrate_ns / options.transitions) << ','
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
