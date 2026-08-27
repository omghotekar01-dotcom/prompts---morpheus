#pragma once

#include <atomic>
#include <cstdint>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace morpheus {

// Native C++20 in-process RCU-style version slot.
//
// Readers acquire an immutable shared_ptr lease with no transition mutex. A
// writer stages a fully constructed payload off-path and atomically publishes a
// new Version under a short transition mutex. Old readers keep the old payload
// alive through shared ownership. Rollback publishes the previous payload as a
// new monotonically increasing generation.
//
// Truth boundary: this establishes native in-process pointer/version switching.
// It does not migrate records between processes, serialize arbitrary structures,
// coordinate distributed replicas, or prove lock-free mutation of the payload.
template <typename Payload>
class VersionedSlot {
public:
    struct Version {
        std::uint64_t generation{};
        std::string candidate_id;
        std::shared_ptr<const Payload> payload;
    };

    VersionedSlot(std::string candidate_id, std::shared_ptr<const Payload> payload) {
        if (candidate_id.empty()) throw std::invalid_argument("candidate_id cannot be empty");
        if (!payload) throw std::invalid_argument("payload cannot be null");
        auto initial = std::make_shared<const Version>(Version{1, std::move(candidate_id), std::move(payload)});
        active_.store(std::move(initial), std::memory_order_release);
    }

    [[nodiscard]] std::shared_ptr<const Version> lease() const noexcept {
        return active_.load(std::memory_order_acquire);
    }

    [[nodiscard]] std::uint64_t activate(
        const std::string& expected_from_candidate_id,
        std::string to_candidate_id,
        std::shared_ptr<const Payload> payload
    ) {
        if (to_candidate_id.empty()) throw std::invalid_argument("target candidate_id cannot be empty");
        if (!payload) throw std::invalid_argument("target payload cannot be null");

        std::lock_guard<std::mutex> guard(transition_mutex_);
        auto current = active_.load(std::memory_order_acquire);
        if (!current) throw std::logic_error("version slot has no active version");
        if (current->candidate_id != expected_from_candidate_id) {
            throw std::runtime_error("active candidate changed before native activation");
        }
        if (current->candidate_id == to_candidate_id) {
            throw std::invalid_argument("target candidate must differ from active candidate");
        }

        rollback_.push_back(current);
        auto replacement = std::make_shared<const Version>(
            Version{current->generation + 1, std::move(to_candidate_id), std::move(payload)}
        );
        const auto generation = replacement->generation;
        active_.store(std::move(replacement), std::memory_order_release);
        return generation;
    }

    [[nodiscard]] std::uint64_t rollback(const std::string& expected_current_candidate_id) {
        std::lock_guard<std::mutex> guard(transition_mutex_);
        auto current = active_.load(std::memory_order_acquire);
        if (!current) throw std::logic_error("version slot has no active version");
        if (current->candidate_id != expected_current_candidate_id) {
            throw std::runtime_error("active candidate changed before native rollback");
        }
        if (rollback_.empty()) throw std::runtime_error("no native version is available for rollback");

        auto previous = rollback_.back();
        rollback_.pop_back();
        auto restored = std::make_shared<const Version>(Version{
            current->generation + 1,
            previous->candidate_id,
            previous->payload,
        });
        const auto generation = restored->generation;
        active_.store(std::move(restored), std::memory_order_release);
        return generation;
    }

    [[nodiscard]] std::size_t rollback_depth() const {
        std::lock_guard<std::mutex> guard(transition_mutex_);
        return rollback_.size();
    }

private:
    std::atomic<std::shared_ptr<const Version>> active_;
    mutable std::mutex transition_mutex_;
    std::vector<std::shared_ptr<const Version>> rollback_;
};

}  // namespace morpheus
