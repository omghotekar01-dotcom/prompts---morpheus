#include "morpheus/versioned_slot.hpp"

#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <memory>
#include <string>
#include <thread>
#include <vector>

struct Payload {
    int marker{};
    std::vector<int> values;
};

int main() {
    using Slot = morpheus::VersionedSlot<Payload>;

    auto payload_a = std::make_shared<const Payload>(Payload{1, {1, 2, 3}});
    Slot slot("candidate-a", payload_a);

    auto first_lease = slot.lease();
    assert(first_lease);
    assert(first_lease->generation == 1);
    assert(first_lease->candidate_id == "candidate-a");
    assert(first_lease->payload->marker == 1);

    std::atomic<bool> stop{false};
    std::atomic<std::uint64_t> reads{0};
    std::atomic<std::uint64_t> invalid{0};
    std::vector<std::thread> readers;
    for (int i = 0; i < 6; ++i) {
        readers.emplace_back([&] {
            while (!stop.load(std::memory_order_relaxed)) {
                auto lease = slot.lease();
                if (!lease || !lease->payload) {
                    invalid.fetch_add(1, std::memory_order_relaxed);
                    continue;
                }
                if (lease->candidate_id == "candidate-a") {
                    if (lease->payload->marker != 1) invalid.fetch_add(1, std::memory_order_relaxed);
                } else if (lease->candidate_id == "candidate-b") {
                    if (lease->payload->marker != 2) invalid.fetch_add(1, std::memory_order_relaxed);
                } else {
                    invalid.fetch_add(1, std::memory_order_relaxed);
                }
                reads.fetch_add(1, std::memory_order_relaxed);
            }
        });
    }

    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    auto payload_b = std::make_shared<const Payload>(Payload{2, {4, 5, 6, 7}});
    const auto generation_two = slot.activate("candidate-a", "candidate-b", payload_b);
    assert(generation_two == 2);
    assert(slot.rollback_depth() == 1);

    auto second_lease = slot.lease();
    assert(second_lease->generation == 2);
    assert(second_lease->candidate_id == "candidate-b");
    assert(second_lease->payload->marker == 2);

    // Existing readers retain snapshot semantics even after publication.
    assert(first_lease->candidate_id == "candidate-a");
    assert(first_lease->payload->marker == 1);

    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    const auto generation_three = slot.rollback("candidate-b");
    assert(generation_three == 3);
    assert(slot.rollback_depth() == 0);

    auto restored = slot.lease();
    assert(restored->generation == 3);
    assert(restored->candidate_id == "candidate-a");
    assert(restored->payload->marker == 1);

    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    stop.store(true, std::memory_order_relaxed);
    for (auto& reader : readers) reader.join();

    assert(reads.load(std::memory_order_relaxed) > 0);
    assert(invalid.load(std::memory_order_relaxed) == 0);

    bool stale_activation_rejected = false;
    try {
        (void)slot.activate("candidate-b", "candidate-c", std::make_shared<const Payload>(Payload{3, {8}}));
    } catch (const std::runtime_error&) {
        stale_activation_rejected = true;
    }
    assert(stale_activation_rejected);

    return 0;
}
