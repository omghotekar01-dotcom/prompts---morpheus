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
                } else if (lease->candidate_id == "candidate-c") {
                    if (lease->payload->marker != 3) invalid.fetch_add(1, std::memory_order_relaxed);
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

    // A rejected staged payload must not change the active generation or
    // rollback history.
    bool shadow_rejected = false;
    try {
        (void)slot.activate_validated(
            "candidate-a",
            "candidate-c",
            std::make_shared<const Payload>(Payload{99, {8, 9}}),
            [](const Payload& current, const Payload& staged) {
                return staged.marker == current.marker + 2 && staged.values.size() >= current.values.size();
            }
        );
    } catch (const std::runtime_error&) {
        shadow_rejected = true;
    }
    assert(shadow_rejected);
    assert(slot.lease()->generation == 3);
    assert(slot.lease()->candidate_id == "candidate-a");
    assert(slot.rollback_depth() == 0);

    // A validated staged payload is atomically published only after the
    // validator succeeds. Readers should observe either complete version.
    const auto generation_four = slot.activate_validated(
        "candidate-a",
        "candidate-c",
        std::make_shared<const Payload>(Payload{3, {1, 2, 3, 8}}),
        [](const Payload& current, const Payload& staged) {
            return staged.marker == current.marker + 2 && staged.values.size() >= current.values.size();
        }
    );
    assert(generation_four == 4);
    assert(slot.rollback_depth() == 1);
    auto validated = slot.lease();
    assert(validated->candidate_id == "candidate-c");
    assert(validated->payload->marker == 3);

    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    const auto generation_five = slot.rollback("candidate-c");
    assert(generation_five == 5);
    assert(slot.lease()->candidate_id == "candidate-a");
    assert(slot.rollback_depth() == 0);

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

    // ABA defense: validation observes candidate A/generation 1. During the
    // validator callback another transition performs A -> B -> A, restoring the
    // same candidate identity but at generation 3. Publication must reject the
    // stale validation result even though the candidate ID is again A.
    {
        auto aba_a = std::make_shared<const Payload>(Payload{10, {10, 11}});
        auto aba_b = std::make_shared<const Payload>(Payload{20, {20, 21}});
        auto aba_c = std::make_shared<const Payload>(Payload{30, {30, 31}});
        Slot aba_slot("candidate-a", aba_a);

        bool aba_rejected = false;
        try {
            (void)aba_slot.activate_validated(
                "candidate-a",
                "candidate-c",
                aba_c,
                [&](const Payload& current, const Payload& staged) {
                    assert(current.marker == 10);
                    assert(staged.marker == 30);
                    assert(aba_slot.activate("candidate-a", "candidate-b", aba_b) == 2);
                    assert(aba_slot.rollback("candidate-b") == 3);
                    return true;
                }
            );
        } catch (const std::runtime_error&) {
            aba_rejected = true;
        }
        assert(aba_rejected);
        const auto after_aba = aba_slot.lease();
        assert(after_aba->candidate_id == "candidate-a");
        assert(after_aba->generation == 3);
        assert(after_aba->payload->marker == 10);
        assert(aba_slot.rollback_depth() == 0);
    }

    return 0;
}
