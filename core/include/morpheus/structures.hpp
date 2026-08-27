#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace morpheus {

// Minimal real Robin-Hood open-addressing index used by the P2 primitive laboratory.
// It is intentionally small and testable; production concurrency/persistence arrive later.
template <typename Key, typename Value, typename Hash = std::hash<Key>, typename Eq = std::equal_to<Key>>
class RobinHoodHashIndex {
public:
    explicit RobinHoodHashIndex(std::size_t initial_capacity = 16) {
        reserve(std::max<std::size_t>(initial_capacity, 8));
    }

    void insert_or_assign(const Key& key, const Value& value) {
        if ((size_ + 1.0) / buckets_.size() > max_load_factor_) {
            rehash(buckets_.size() * 2);
        }
        insert_impl(key, value);
    }

    [[nodiscard]] const Value* find(const Key& key) const noexcept {
        if (buckets_.empty()) return nullptr;
        std::size_t index = bucket_for(key);
        std::size_t distance = 0;
        while (true) {
            const Bucket& bucket = buckets_[index];
            if (!bucket.entry.has_value() || bucket.distance < distance) return nullptr;
            if (eq_(bucket.entry->first, key)) return &bucket.entry->second;
            index = (index + 1) % buckets_.size();
            ++distance;
            if (distance >= buckets_.size()) return nullptr;
        }
    }

    bool erase(const Key& key) {
        if (buckets_.empty()) return false;
        std::size_t index = bucket_for(key);
        std::size_t distance = 0;
        while (true) {
            Bucket& bucket = buckets_[index];
            if (!bucket.entry.has_value() || bucket.distance < distance) return false;
            if (eq_(bucket.entry->first, key)) break;
            index = (index + 1) % buckets_.size();
            ++distance;
            if (distance >= buckets_.size()) return false;
        }

        std::size_t current = index;
        std::size_t next = (current + 1) % buckets_.size();
        while (buckets_[next].entry.has_value() && buckets_[next].distance > 0) {
            buckets_[current].entry = std::move(buckets_[next].entry);
            buckets_[current].distance = buckets_[next].distance - 1;
            current = next;
            next = (next + 1) % buckets_.size();
        }
        buckets_[current].entry.reset();
        buckets_[current].distance = 0;
        --size_;
        return true;
    }

    [[nodiscard]] std::size_t size() const noexcept { return size_; }
    [[nodiscard]] std::size_t capacity() const noexcept { return buckets_.size(); }
    [[nodiscard]] std::size_t memory_usage_bytes() const noexcept { return buckets_.capacity() * sizeof(Bucket); }

private:
    struct Bucket {
        std::optional<std::pair<Key, Value>> entry;
        std::size_t distance = 0;
    };

    std::vector<Bucket> buckets_;
    std::size_t size_ = 0;
    Hash hash_{};
    Eq eq_{};
    static constexpr double max_load_factor_ = 0.80;

    [[nodiscard]] std::size_t bucket_for(const Key& key) const noexcept {
        return hash_(key) % buckets_.size();
    }

    void reserve(std::size_t requested) {
        std::size_t capacity = 8;
        while (capacity < requested) capacity *= 2;
        buckets_.assign(capacity, Bucket{});
    }

    void rehash(std::size_t requested) {
        auto old = std::move(buckets_);
        reserve(requested);
        size_ = 0;
        for (auto& bucket : old) {
            if (bucket.entry.has_value()) {
                insert_impl(bucket.entry->first, bucket.entry->second);
            }
        }
    }

    void insert_impl(Key key, Value value) {
        std::size_t index = bucket_for(key);
        std::size_t distance = 0;
        std::pair<Key, Value> incoming{std::move(key), std::move(value)};

        while (distance < buckets_.size()) {
            Bucket& bucket = buckets_[index];
            if (!bucket.entry.has_value()) {
                bucket.entry = std::move(incoming);
                bucket.distance = distance;
                ++size_;
                return;
            }
            if (eq_(bucket.entry->first, incoming.first)) {
                bucket.entry->second = std::move(incoming.second);
                return;
            }
            if (bucket.distance < distance) {
                std::swap(bucket.entry.value(), incoming);
                std::swap(bucket.distance, distance);
            }
            index = (index + 1) % buckets_.size();
            ++distance;
        }
        throw std::runtime_error("RobinHoodHashIndex insertion failed: table unexpectedly full");
    }
};


template <typename Key, typename Value>
class OrderedTreeIndex {
public:
    void insert_or_assign(const Key& key, const Value& value) { data_[key] = value; }
    bool erase(const Key& key) { return data_.erase(key) != 0; }

    [[nodiscard]] const Value* find(const Key& key) const noexcept {
        auto it = data_.find(key);
        return it == data_.end() ? nullptr : &it->second;
    }

    [[nodiscard]] std::vector<Value> range(const Key& low, const Key& high) const {
        std::vector<Value> out;
        for (auto it = data_.lower_bound(low); it != data_.end() && !(high < it->first); ++it) {
            out.push_back(it->second);
        }
        return out;
    }

    [[nodiscard]] std::size_t size() const noexcept { return data_.size(); }

private:
    std::map<Key, Value> data_;
};


template <typename Key, typename Value>
class SortedArrayIndex {
public:
    void bulk_load(std::vector<std::pair<Key, Value>> rows) {
        std::sort(rows.begin(), rows.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
        rows_ = std::move(rows);
    }

    void insert_or_assign(const Key& key, const Value& value) {
        auto it = lower_bound(key);
        if (it != rows_.end() && !(key < it->first) && !(it->first < key)) {
            it->second = value;
        } else {
            rows_.insert(it, {key, value});
        }
    }

    [[nodiscard]] const Value* find(const Key& key) const noexcept {
        auto it = lower_bound_const(key);
        if (it == rows_.end() || key < it->first || it->first < key) return nullptr;
        return &it->second;
    }

    [[nodiscard]] std::vector<Value> range(const Key& low, const Key& high) const {
        std::vector<Value> out;
        for (auto it = lower_bound_const(low); it != rows_.end() && !(high < it->first); ++it) {
            out.push_back(it->second);
        }
        return out;
    }

    [[nodiscard]] std::size_t size() const noexcept { return rows_.size(); }

private:
    std::vector<std::pair<Key, Value>> rows_;

    auto lower_bound(const Key& key) {
        return std::lower_bound(rows_.begin(), rows_.end(), key, [](const auto& row, const Key& value) {
            return row.first < value;
        });
    }

    auto lower_bound_const(const Key& key) const {
        return std::lower_bound(rows_.begin(), rows_.end(), key, [](const auto& row, const Key& value) {
            return row.first < value;
        });
    }
};


template <typename Value>
class PrefixTrie {
public:
    void insert_or_assign(const std::string& key, const Value& value) {
        Node* node = &root_;
        for (char ch : key) {
            auto& next = node->children[ch];
            if (!next) next = std::make_unique<Node>();
            node = next.get();
        }
        if (!node->value.has_value()) ++size_;
        node->value = value;
    }

    [[nodiscard]] const Value* find(const std::string& key) const noexcept {
        const Node* node = descend(key);
        return node && node->value.has_value() ? &node->value.value() : nullptr;
    }

    [[nodiscard]] std::vector<Value> prefix_search(const std::string& prefix, std::size_t limit = 100) const {
        std::vector<Value> out;
        const Node* node = descend(prefix);
        if (!node) return out;
        collect(*node, out, limit);
        return out;
    }

    [[nodiscard]] std::size_t size() const noexcept { return size_; }

private:
    struct Node {
        std::unordered_map<char, std::unique_ptr<Node>> children;
        std::optional<Value> value;
    };

    Node root_;
    std::size_t size_ = 0;

    [[nodiscard]] const Node* descend(const std::string& key) const noexcept {
        const Node* node = &root_;
        for (char ch : key) {
            auto it = node->children.find(ch);
            if (it == node->children.end()) return nullptr;
            node = it->second.get();
        }
        return node;
    }

    static void collect(const Node& node, std::vector<Value>& out, std::size_t limit) {
        if (out.size() >= limit) return;
        if (node.value.has_value()) out.push_back(node.value.value());
        if (out.size() >= limit) return;
        // Stable traversal for deterministic test/replay behavior.
        std::vector<char> keys;
        keys.reserve(node.children.size());
        for (const auto& [ch, _] : node.children) keys.push_back(ch);
        std::sort(keys.begin(), keys.end());
        for (char ch : keys) {
            collect(*node.children.at(ch), out, limit);
            if (out.size() >= limit) return;
        }
    }
};


template <typename Category, typename RecordId = std::uint32_t>
class BitmapFilterIndex {
public:
    void add(const Category& category, RecordId id) {
        auto& ids = postings_[category];
        if (std::find(ids.begin(), ids.end(), id) == ids.end()) ids.push_back(id);
    }

    bool remove(const Category& category, RecordId id) {
        auto it = postings_.find(category);
        if (it == postings_.end()) return false;
        auto& ids = it->second;
        auto target = std::find(ids.begin(), ids.end(), id);
        if (target == ids.end()) return false;
        ids.erase(target);
        if (ids.empty()) postings_.erase(it);
        return true;
    }

    [[nodiscard]] std::vector<RecordId> filter(const Category& category) const {
        auto it = postings_.find(category);
        return it == postings_.end() ? std::vector<RecordId>{} : it->second;
    }

private:
    // P2 uses compact posting vectors as the correctness baseline. A compressed roaring container is a later optimization.
    std::unordered_map<Category, std::vector<RecordId>> postings_;
};

}  // namespace morpheus
