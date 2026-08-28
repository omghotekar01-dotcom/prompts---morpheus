#include "morpheus/erased_versioned_slot.hpp"

#include <atomic>
#include <cassert>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <thread>

struct PayloadA { std::uint64_t value{}; };
struct PayloadB { std::uint64_t value{}; };
struct PayloadC { std::uint64_t value{}; };

int main() {
    auto initial = std::make_shared<PayloadA>(PayloadA{1});
    morpheus::ErasedVersionedSlot slot("candidate-a", std::shared_ptr<const PayloadA>(initial));
    const auto observed = slot.lease();

    std::atomic<int> ready{0};
    std::atomic<bool> go{false};
    std::atomic<int> successes{0};
    std::atomic<int> stale_rejections{0};

    auto publish_b = [&] {
        auto payload = std::make_shared<PayloadB>(PayloadB{2});
        ready.fetch_add(1, std::memory_order_release);
        while (!go.load(std::memory_order_acquire)) std::this_thread::yield();
        try {
            (void)slot.activate_validated(observed, "candidate-b", std::shared_ptr<const PayloadB>(payload), [](const PayloadB&) { return true; });
            successes.fetch_add(1, std::memory_order_relaxed);
        } catch (const std::runtime_error&) {
            stale_rejections.fetch_add(1, std::memory_order_relaxed);
        }
    };
    auto publish_c = [&] {
        auto payload = std::make_shared<PayloadC>(PayloadC{3});
        ready.fetch_add(1, std::memory_order_release);
        while (!go.load(std::memory_order_acquire)) std::this_thread::yield();
        try {
            (void)slot.activate_validated(observed, "candidate-c", std::shared_ptr<const PayloadC>(payload), [](const PayloadC&) { return true; });
            successes.fetch_add(1, std::memory_order_relaxed);
        } catch (const std::runtime_error&) {
            stale_rejections.fetch_add(1, std::memory_order_relaxed);
        }
    };

    std::thread b(publish_b);
    std::thread c(publish_c);
    while (ready.load(std::memory_order_acquire) != 2) std::this_thread::yield();
    go.store(true, std::memory_order_release);
    b.join();
    c.join();

    assert(successes.load() == 1);
    assert(stale_rejections.load() == 1);
    assert(slot.lease()->generation == 2);
    assert(slot.rollback_depth() == 1);
    assert(slot.lease()->candidate_id == "candidate-b" || slot.lease()->candidate_id == "candidate-c");

    const auto winner = slot.lease()->candidate_id;
    assert(slot.rollback(winner) == 3);
    assert(slot.lease()->candidate_id == "candidate-a");
    assert(slot.lease_as<PayloadA>()->value == 1);
    assert(slot.rollback_depth() == 0);
    return 0;
}
