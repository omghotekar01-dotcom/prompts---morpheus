#pragma once

#include <atomic>
#include <cstdint>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <typeindex>
#include <typeinfo>
#include <utility>
#include <vector>

namespace morpheus {

// Type-erased in-process publication slot for cross-configuration migrations.
//
// Unlike VersionedSlot<T>, this slot can publish payloads with different C++
// types across generations. Each immutable Version records std::type_index so a
// reader can request lease_as<T>() safely. Publication requires the exact
// previously observed Version (candidate id + generation), closing ABA windows
// while shadow construction/validation happens off-path.
//
// Truth boundary: this is same-process type-erased pointer publication and
// rollback. It is not cross-process ABI serialization, distributed migration or
// a generic query-dispatch interface; callers still need candidate-aware query
// dispatch after acquiring the typed lease.
class ErasedVersionedSlot {
public:
    struct Version {
        std::uint64_t generation{};
        std::string candidate_id;
        std::type_index payload_type{typeid(void)};
        std::shared_ptr<const void> payload;
    };

    template <typename Payload>
    ErasedVersionedSlot(std::string candidate_id, std::shared_ptr<const Payload> payload) {
        if (candidate_id.empty()) throw std::invalid_argument("candidate_id cannot be empty");
        if (!payload) throw std::invalid_argument("payload cannot be null");
        auto initial = std::make_shared<const Version>(Version{
            1,
            std::move(candidate_id),
            std::type_index(typeid(Payload)),
            std::shared_ptr<const void>(std::move(payload)),
        });
        active_.store(std::move(initial), std::memory_order_release);
    }

    [[nodiscard]] std::shared_ptr<const Version> lease() const noexcept {
        return active_.load(std::memory_order_acquire);
    }

    template <typename Payload>
    [[nodiscard]] std::shared_ptr<const Payload> lease_as() const {
        const auto version = lease();
        if (!version || !version->payload) throw std::logic_error("version slot has no active payload");
        if (version->payload_type != std::type_index(typeid(Payload))) {
            throw std::bad_cast();
        }
        return std::shared_ptr<const Payload>(
            version->payload,
            static_cast<const Payload*>(version->payload.get())
        );
    }

    template <typename Payload, typename Validator>
    [[nodiscard]] std::uint64_t activate_validated(
        const std::shared_ptr<const Version>& expected_version,
        std::string to_candidate_id,
        std::shared_ptr<const Payload> payload,
        Validator&& validator
    ) {
        if (!expected_version) throw std::invalid_argument("expected_version cannot be null");
        if (to_candidate_id.empty()) throw std::invalid_argument("target candidate_id cannot be empty");
        if (!payload) throw std::invalid_argument("target payload cannot be null");
        if (!std::forward<Validator>(validator)(*payload)) {
            throw std::runtime_error("native erased shadow validation rejected target candidate");
        }

        std::lock_guard<std::mutex> guard(transition_mutex_);
        const auto current = active_.load(std::memory_order_acquire);
        if (!current) throw std::logic_error("version slot has no active version");
        if (current->candidate_id != expected_version->candidate_id || current->generation != expected_version->generation) {
            throw std::runtime_error("active version changed after erased shadow validation");
        }
        if (current->candidate_id == to_candidate_id) {
            throw std::invalid_argument("target candidate must differ from active candidate");
        }

        rollback_.push_back(current);
        auto replacement = std::make_shared<const Version>(Version{
            current->generation + 1,
            std::move(to_candidate_id),
            std::type_index(typeid(Payload)),
            std::shared_ptr<const void>(std::move(payload)),
        });
        const auto generation = replacement->generation;
        active_.store(std::move(replacement), std::memory_order_release);
        return generation;
    }

    [[nodiscard]] std::uint64_t rollback(const std::string& expected_current_candidate_id) {
        std::lock_guard<std::mutex> guard(transition_mutex_);
        const auto current = active_.load(std::memory_order_acquire);
        if (!current) throw std::logic_error("version slot has no active version");
        if (current->candidate_id != expected_current_candidate_id) {
            throw std::runtime_error("active candidate changed before erased rollback");
        }
        if (rollback_.empty()) throw std::runtime_error("no erased version is available for rollback");

        auto previous = rollback_.back();
        rollback_.pop_back();
        auto restored = std::make_shared<const Version>(Version{
            current->generation + 1,
            previous->candidate_id,
            previous->payload_type,
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
