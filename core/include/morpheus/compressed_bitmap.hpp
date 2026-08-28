#pragma once

#include <algorithm>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <iterator>
#include <type_traits>
#include <unordered_map>
#include <utility>
#include <vector>

namespace morpheus {

template <
    typename RecordId = std::uint32_t,
    std::size_t PromoteThreshold = 4096,
    std::size_t DemoteThreshold = 2048
>
class CompressedBitmap {
    static_assert(std::is_unsigned_v<RecordId>, "CompressedBitmap requires an unsigned RecordId");
    static_assert(sizeof(RecordId) <= sizeof(std::uint32_t), "CompressedBitmap currently supports up to 32-bit ids");
    static_assert(PromoteThreshold > 0 && PromoteThreshold <= (1U << 16U), "invalid dense promotion threshold");
    static_assert(DemoteThreshold < PromoteThreshold, "demotion threshold must be below promotion threshold");

    class Container {
    public:
        static constexpr std::size_t dense_word_count = 1U << 10U; // 65,536 bits.
        static constexpr std::size_t promote_threshold = PromoteThreshold;
        static constexpr std::size_t demote_threshold = DemoteThreshold;

        [[nodiscard]] bool dense() const noexcept { return !dense_words_.empty(); }
        [[nodiscard]] std::size_t size() const noexcept { return cardinality_; }
        [[nodiscard]] bool empty() const noexcept { return cardinality_ == 0; }

        bool add(std::uint16_t value) {
            if (dense()) {
                const auto word = static_cast<std::size_t>(value) >> 6U;
                const auto mask = std::uint64_t{1} << (value & 63U);
                if ((dense_words_[word] & mask) != 0) return false;
                dense_words_[word] |= mask;
                ++cardinality_;
                return true;
            }

            const auto it = std::lower_bound(sparse_.begin(), sparse_.end(), value);
            if (it != sparse_.end() && *it == value) return false;
            sparse_.insert(it, value);
            ++cardinality_;
            if (cardinality_ >= promote_threshold) promote();
            return true;
        }

        bool remove(std::uint16_t value) {
            if (dense()) {
                const auto word = static_cast<std::size_t>(value) >> 6U;
                const auto mask = std::uint64_t{1} << (value & 63U);
                if ((dense_words_[word] & mask) == 0) return false;
                dense_words_[word] &= ~mask;
                --cardinality_;
                if (cardinality_ <= demote_threshold) demote();
                return true;
            }

            const auto it = std::lower_bound(sparse_.begin(), sparse_.end(), value);
            if (it == sparse_.end() || *it != value) return false;
            sparse_.erase(it);
            --cardinality_;
            return true;
        }

        [[nodiscard]] bool contains(std::uint16_t value) const noexcept {
            if (dense()) {
                const auto word = static_cast<std::size_t>(value) >> 6U;
                const auto mask = std::uint64_t{1} << (value & 63U);
                return (dense_words_[word] & mask) != 0;
            }
            return std::binary_search(sparse_.begin(), sparse_.end(), value);
        }

        [[nodiscard]] std::vector<std::uint16_t> values() const {
            if (!dense()) return sparse_;
            std::vector<std::uint16_t> out;
            out.reserve(cardinality_);
            for (std::size_t word_index = 0; word_index < dense_words_.size(); ++word_index) {
                auto bits = dense_words_[word_index];
                while (bits != 0) {
                    const auto bit = static_cast<unsigned>(std::countr_zero(bits));
                    out.push_back(static_cast<std::uint16_t>((word_index << 6U) + bit));
                    bits &= bits - 1;
                }
            }
            return out;
        }

        [[nodiscard]] Container intersection(const Container& other) const {
            Container out;
            if (dense() && other.dense()) {
                out.dense_words_.assign(dense_word_count, 0);
                for (std::size_t i = 0; i < dense_word_count; ++i) {
                    out.dense_words_[i] = dense_words_[i] & other.dense_words_[i];
                    out.cardinality_ += static_cast<std::size_t>(std::popcount(out.dense_words_[i]));
                }
                if (out.cardinality_ <= demote_threshold) out.demote();
                return out;
            }

            if (!dense() && !other.dense()) {
                out.sparse_.reserve(std::min(sparse_.size(), other.sparse_.size()));
                std::set_intersection(sparse_.begin(), sparse_.end(), other.sparse_.begin(), other.sparse_.end(), std::back_inserter(out.sparse_));
                out.cardinality_ = out.sparse_.size();
                return out;
            }

            const auto& sparse_side = dense() ? other : *this;
            const auto& dense_side = dense() ? *this : other;
            out.sparse_.reserve(sparse_side.cardinality_);
            for (const auto value : sparse_side.sparse_) {
                if (dense_side.contains(value)) out.sparse_.push_back(value);
            }
            out.cardinality_ = out.sparse_.size();
            return out;
        }

        [[nodiscard]] Container set_union(const Container& other) const {
            if (dense() || other.dense()) {
                Container out = dense() ? *this : other;
                const auto& remaining = dense() ? other : *this;
                if (remaining.dense()) {
                    for (std::size_t i = 0; i < dense_word_count; ++i) {
                        out.dense_words_[i] |= remaining.dense_words_[i];
                    }
                    out.recount_dense();
                } else {
                    for (const auto value : remaining.sparse_) out.add(value);
                }
                return out;
            }

            Container out;
            out.sparse_.reserve(sparse_.size() + other.sparse_.size());
            std::set_union(sparse_.begin(), sparse_.end(), other.sparse_.begin(), other.sparse_.end(), std::back_inserter(out.sparse_));
            out.cardinality_ = out.sparse_.size();
            if (out.cardinality_ >= promote_threshold) out.promote();
            return out;
        }

    private:
        std::vector<std::uint16_t> sparse_;
        std::vector<std::uint64_t> dense_words_;
        std::size_t cardinality_ = 0;

        void promote() {
            if (dense()) return;
            dense_words_.assign(dense_word_count, 0);
            for (const auto value : sparse_) {
                dense_words_[static_cast<std::size_t>(value) >> 6U] |= std::uint64_t{1} << (value & 63U);
            }
            sparse_.clear();
            sparse_.shrink_to_fit();
        }

        void demote() {
            if (!dense()) return;
            sparse_.clear();
            sparse_.reserve(cardinality_);
            for (std::size_t word_index = 0; word_index < dense_words_.size(); ++word_index) {
                auto bits = dense_words_[word_index];
                while (bits != 0) {
                    const auto bit = static_cast<unsigned>(std::countr_zero(bits));
                    sparse_.push_back(static_cast<std::uint16_t>((word_index << 6U) + bit));
                    bits &= bits - 1;
                }
            }
            dense_words_.clear();
            dense_words_.shrink_to_fit();
        }

        void recount_dense() noexcept {
            cardinality_ = 0;
            for (const auto word : dense_words_) cardinality_ += static_cast<std::size_t>(std::popcount(word));
        }
    };

public:
    static constexpr std::size_t promotion_threshold = PromoteThreshold;
    static constexpr std::size_t demotion_threshold = DemoteThreshold;

    bool add(RecordId id) {
        const auto [high, low] = split(id);
        auto& container = containers_[high];
        if (!container.add(low)) return false;
        ++size_;
        return true;
    }

    bool remove(RecordId id) {
        const auto [high, low] = split(id);
        const auto bucket = containers_.find(high);
        if (bucket == containers_.end() || !bucket->second.remove(low)) return false;
        --size_;
        if (bucket->second.empty()) containers_.erase(bucket);
        return true;
    }

    [[nodiscard]] bool contains(RecordId id) const noexcept {
        const auto [high, low] = split(id);
        const auto bucket = containers_.find(high);
        return bucket != containers_.end() && bucket->second.contains(low);
    }

    [[nodiscard]] std::size_t size() const noexcept { return size_; }
    [[nodiscard]] bool empty() const noexcept { return size_ == 0; }
    [[nodiscard]] std::size_t container_count() const noexcept { return containers_.size(); }
    [[nodiscard]] std::size_t dense_container_count() const noexcept {
        std::size_t count = 0;
        for (const auto& [_, container] : containers_) count += container.dense() ? 1U : 0U;
        return count;
    }

    [[nodiscard]] std::vector<RecordId> values() const {
        std::vector<std::pair<std::uint16_t, const Container*>> ordered;
        ordered.reserve(containers_.size());
        for (const auto& [high, container] : containers_) ordered.emplace_back(high, &container);
        std::sort(ordered.begin(), ordered.end(), [](const auto& a, const auto& b) { return a.first < b.first; });

        std::vector<RecordId> out;
        out.reserve(size_);
        for (const auto& [high, container] : ordered) {
            for (const auto low : container->values()) out.push_back(join(high, low));
        }
        return out;
    }

    [[nodiscard]] CompressedBitmap intersection(const CompressedBitmap& other) const {
        CompressedBitmap out;
        const auto& smaller = containers_.size() <= other.containers_.size() ? containers_ : other.containers_;
        const auto& larger = containers_.size() <= other.containers_.size() ? other.containers_ : containers_;
        out.containers_.reserve(smaller.size());
        for (const auto& [high, left] : smaller) {
            const auto right = larger.find(high);
            if (right == larger.end()) continue;
            auto merged = left.intersection(right->second);
            if (merged.empty()) continue;
            out.size_ += merged.size();
            out.containers_.emplace(high, std::move(merged));
        }
        return out;
    }

    [[nodiscard]] CompressedBitmap set_union(const CompressedBitmap& other) const {
        CompressedBitmap out;
        out.containers_.reserve(containers_.size() + other.containers_.size());
        for (const auto& [high, left] : containers_) {
            const auto right = other.containers_.find(high);
            if (right == other.containers_.end()) {
                out.size_ += left.size();
                out.containers_.emplace(high, left);
                continue;
            }
            auto merged = left.set_union(right->second);
            out.size_ += merged.size();
            out.containers_.emplace(high, std::move(merged));
        }
        for (const auto& [high, right] : other.containers_) {
            if (containers_.find(high) != containers_.end()) continue;
            out.size_ += right.size();
            out.containers_.emplace(high, right);
        }
        return out;
    }

private:
    std::unordered_map<std::uint16_t, Container> containers_;
    std::size_t size_ = 0;

    static constexpr std::pair<std::uint16_t, std::uint16_t> split(RecordId id) noexcept {
        const auto value = static_cast<std::uint32_t>(id);
        return {static_cast<std::uint16_t>(value >> 16U), static_cast<std::uint16_t>(value & 0xFFFFU)};
    }

    static constexpr RecordId join(std::uint16_t high, std::uint16_t low) noexcept {
        return static_cast<RecordId>((static_cast<std::uint32_t>(high) << 16U) | low);
    }
};

template <typename Category, typename RecordId = std::uint32_t>
class CompressedBitmapFilterIndex {
public:
    bool add(const Category& category, RecordId id) { return postings_[category].add(id); }

    bool remove(const Category& category, RecordId id) {
        auto it = postings_.find(category);
        if (it == postings_.end() || !it->second.remove(id)) return false;
        if (it->second.empty()) postings_.erase(it);
        return true;
    }

    [[nodiscard]] bool contains(const Category& category, RecordId id) const noexcept {
        const auto it = postings_.find(category);
        return it != postings_.end() && it->second.contains(id);
    }

    [[nodiscard]] std::vector<RecordId> filter(const Category& category) const {
        const auto it = postings_.find(category);
        return it == postings_.end() ? std::vector<RecordId>{} : it->second.values();
    }

    [[nodiscard]] std::vector<RecordId> filter_all(const Category& a, const Category& b) const {
        const auto left = postings_.find(a);
        const auto right = postings_.find(b);
        if (left == postings_.end() || right == postings_.end()) return {};
        return left->second.intersection(right->second).values();
    }

private:
    std::unordered_map<Category, CompressedBitmap<RecordId>> postings_;
};

} // namespace morpheus
