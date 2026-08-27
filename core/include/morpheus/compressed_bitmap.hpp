#pragma once

#include <algorithm>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <unordered_map>
#include <utility>
#include <vector>

namespace morpheus {

// A dependency-free, correctness-first compressed bitmap using sorted 16-bit
// array containers. The public shape deliberately mirrors the subset of
// Roaring-style semantics MORPHEUS needs today while keeping the representation
// explicit and portable. Dense bitset/run containers can be added behind this
// interface after measured crossover experiments.
template <typename RecordId = std::uint32_t>
class CompressedBitmap {
    static_assert(std::is_unsigned_v<RecordId>, "CompressedBitmap requires an unsigned RecordId");
    static_assert(sizeof(RecordId) <= sizeof(std::uint32_t), "CompressedBitmap currently supports up to 32-bit ids");

public:
    bool add(RecordId id) {
        const auto [high, low] = split(id);
        auto& values = containers_[high];
        const auto it = std::lower_bound(values.begin(), values.end(), low);
        if (it != values.end() && *it == low) return false;
        values.insert(it, low);
        ++size_;
        return true;
    }

    bool remove(RecordId id) {
        const auto [high, low] = split(id);
        auto bucket = containers_.find(high);
        if (bucket == containers_.end()) return false;
        auto& values = bucket->second;
        const auto it = std::lower_bound(values.begin(), values.end(), low);
        if (it == values.end() || *it != low) return false;
        values.erase(it);
        --size_;
        if (values.empty()) containers_.erase(bucket);
        return true;
    }

    [[nodiscard]] bool contains(RecordId id) const noexcept {
        const auto [high, low] = split(id);
        const auto bucket = containers_.find(high);
        if (bucket == containers_.end()) return false;
        return std::binary_search(bucket->second.begin(), bucket->second.end(), low);
    }

    [[nodiscard]] std::size_t size() const noexcept { return size_; }
    [[nodiscard]] bool empty() const noexcept { return size_ == 0; }
    [[nodiscard]] std::size_t container_count() const noexcept { return containers_.size(); }

    [[nodiscard]] std::vector<RecordId> values() const {
        std::vector<std::pair<std::uint16_t, const std::vector<std::uint16_t>*>> ordered;
        ordered.reserve(containers_.size());
        for (const auto& [high, lows] : containers_) ordered.emplace_back(high, &lows);
        std::sort(ordered.begin(), ordered.end(), [](const auto& a, const auto& b) { return a.first < b.first; });

        std::vector<RecordId> out;
        out.reserve(size_);
        for (const auto& [high, lows] : ordered) {
            for (const auto low : *lows) out.push_back(join(high, low));
        }
        return out;
    }

    [[nodiscard]] CompressedBitmap intersection(const CompressedBitmap& other) const {
        CompressedBitmap out;
        for (const auto& [high, left] : containers_) {
            const auto right_it = other.containers_.find(high);
            if (right_it == other.containers_.end()) continue;
            std::vector<std::uint16_t> merged;
            merged.reserve(std::min(left.size(), right_it->second.size()));
            std::set_intersection(left.begin(), left.end(), right_it->second.begin(), right_it->second.end(), std::back_inserter(merged));
            if (!merged.empty()) {
                out.size_ += merged.size();
                out.containers_.emplace(high, std::move(merged));
            }
        }
        return out;
    }

    [[nodiscard]] CompressedBitmap set_union(const CompressedBitmap& other) const {
        CompressedBitmap out = *this;
        for (const auto id : other.values()) out.add(id);
        return out;
    }

private:
    std::unordered_map<std::uint16_t, std::vector<std::uint16_t>> containers_;
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
        if (it == postings_.end()) return false;
        if (!it->second.remove(id)) return false;
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

}  // namespace morpheus
