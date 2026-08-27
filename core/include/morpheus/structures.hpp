#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <iterator>
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


// A compact B+ tree implementation used as MORPHEUS's ordered primitive.
//
// - Point lookups descend internal separator nodes.
// - Range scans walk a linked leaf chain.
// - Inserts split leaves/internal nodes and can grow the root.
// - Erase is deliberately correctness-first: it rebuilds the tree from the
//   remaining sorted leaf contents instead of implementing merge/redistribution.
//   This preserves real B+ tree read/insert behavior while keeping deletion
//   semantics auditable until a full rebalancing delete path is implemented.
template <typename Key, typename Value, std::size_t MaxKeys = 31>
class OrderedTreeIndex {
    static_assert(MaxKeys >= 3, "B+ tree MaxKeys must be at least 3");

public:
    OrderedTreeIndex() : root_(std::make_unique<Node>(true)) {}

    void insert_or_assign(const Key& key, const Value& value) {
        auto split = insert_recursive(*root_, key, value);
        if (!split.has_value()) return;

        auto new_root = std::make_unique<Node>(false);
        new_root->keys.push_back(split->separator);
        new_root->children.push_back(std::move(root_));
        new_root->children.push_back(std::move(split->right));
        root_ = std::move(new_root);
    }

    bool erase(const Key& key) {
        if (find(key) == nullptr) return false;
        auto rows = items();
        root_ = std::make_unique<Node>(true);
        size_ = 0;
        for (const auto& [existing_key, existing_value] : rows) {
            if (!equal_key(existing_key, key)) insert_or_assign(existing_key, existing_value);
        }
        return true;
    }

    [[nodiscard]] const Value* find(const Key& key) const noexcept {
        const Node* leaf = find_leaf(key);
        if (!leaf) return nullptr;
        const auto it = std::lower_bound(leaf->keys.begin(), leaf->keys.end(), key, less_);
        if (it == leaf->keys.end() || !equal_key(*it, key)) return nullptr;
        const auto index = static_cast<std::size_t>(std::distance(leaf->keys.begin(), it));
        return &leaf->values[index];
    }

    [[nodiscard]] std::vector<Value> range(const Key& low, const Key& high) const {
        std::vector<Value> out;
        if (less_(high, low)) return out;
        const Node* leaf = find_leaf(low);
        if (!leaf) return out;

        bool first_leaf = true;
        while (leaf) {
            std::size_t begin = 0;
            if (first_leaf) {
                begin = static_cast<std::size_t>(
                    std::distance(leaf->keys.begin(), std::lower_bound(leaf->keys.begin(), leaf->keys.end(), low, less_))
                );
                first_leaf = false;
            }
            for (std::size_t i = begin; i < leaf->keys.size(); ++i) {
                if (less_(high, leaf->keys[i])) return out;
                out.push_back(leaf->values[i]);
            }
            leaf = leaf->next;
        }
        return out;
    }

    [[nodiscard]] std::size_t size() const noexcept { return size_; }

    [[nodiscard]] std::size_t height() const noexcept {
        std::size_t result = 0;
        const Node* node = root_.get();
        while (node) {
            ++result;
            if (node->leaf || node->children.empty()) break;
            node = node->children.front().get();
        }
        return result;
    }

    [[nodiscard]] std::vector<std::pair<Key, Value>> items() const {
        std::vector<std::pair<Key, Value>> out;
        out.reserve(size_);
        const Node* leaf = leftmost_leaf();
        while (leaf) {
            for (std::size_t i = 0; i < leaf->keys.size(); ++i) {
                out.emplace_back(leaf->keys[i], leaf->values[i]);
            }
            leaf = leaf->next;
        }
        return out;
    }

    [[nodiscard]] bool validate() const noexcept {
        if (!root_) return false;
        if (!validate_node(*root_, true)) return false;

        const Node* leaf = leftmost_leaf();
        std::size_t count = 0;
        const Key* previous = nullptr;
        while (leaf) {
            if (!leaf->leaf || leaf->keys.size() != leaf->values.size()) return false;
            for (const auto& key : leaf->keys) {
                if (previous && !less_(*previous, key)) return false;
                previous = &key;
                ++count;
            }
            leaf = leaf->next;
        }
        return count == size_;
    }

private:
    struct Node {
        explicit Node(bool is_leaf) : leaf(is_leaf) {}
        bool leaf;
        std::vector<Key> keys;
        std::vector<Value> values;
        std::vector<std::unique_ptr<Node>> children;
        Node* next = nullptr;
    };

    struct Split {
        Key separator;
        std::unique_ptr<Node> right;
    };

    std::unique_ptr<Node> root_;
    std::size_t size_ = 0;
    std::less<Key> less_{};

    [[nodiscard]] bool equal_key(const Key& left, const Key& right) const noexcept {
        return !less_(left, right) && !less_(right, left);
    }

    [[nodiscard]] const Node* find_leaf(const Key& key) const noexcept {
        const Node* node = root_.get();
        while (node && !node->leaf) {
            const auto it = std::upper_bound(node->keys.begin(), node->keys.end(), key, less_);
            const auto child_index = static_cast<std::size_t>(std::distance(node->keys.begin(), it));
            if (child_index >= node->children.size()) return nullptr;
            node = node->children[child_index].get();
        }
        return node;
    }

    [[nodiscard]] const Node* leftmost_leaf() const noexcept {
        const Node* node = root_.get();
        while (node && !node->leaf) {
            if (node->children.empty()) return nullptr;
            node = node->children.front().get();
        }
        return node;
    }

    std::optional<Split> insert_recursive(Node& node, const Key& key, const Value& value) {
        if (node.leaf) {
            const auto it = std::lower_bound(node.keys.begin(), node.keys.end(), key, less_);
            const auto index = static_cast<std::size_t>(std::distance(node.keys.begin(), it));
            if (it != node.keys.end() && equal_key(*it, key)) {
                node.values[index] = value;
                return std::nullopt;
            }

            node.keys.insert(it, key);
            node.values.insert(node.values.begin() + static_cast<std::ptrdiff_t>(index), value);
            ++size_;
            if (node.keys.size() <= MaxKeys) return std::nullopt;
            return split_leaf(node);
        }

        const auto child_it = std::upper_bound(node.keys.begin(), node.keys.end(), key, less_);
        const auto child_index = static_cast<std::size_t>(std::distance(node.keys.begin(), child_it));
        auto child_split = insert_recursive(*node.children.at(child_index), key, value);
        if (!child_split.has_value()) return std::nullopt;

        node.keys.insert(node.keys.begin() + static_cast<std::ptrdiff_t>(child_index), child_split->separator);
        node.children.insert(
            node.children.begin() + static_cast<std::ptrdiff_t>(child_index + 1),
            std::move(child_split->right)
        );
        if (node.keys.size() <= MaxKeys) return std::nullopt;
        return split_internal(node);
    }

    Split split_leaf(Node& node) {
        const std::size_t midpoint = node.keys.size() / 2;
        auto right = std::make_unique<Node>(true);
        right->keys.assign(
            std::make_move_iterator(node.keys.begin() + static_cast<std::ptrdiff_t>(midpoint)),
            std::make_move_iterator(node.keys.end())
        );
        right->values.assign(
            std::make_move_iterator(node.values.begin() + static_cast<std::ptrdiff_t>(midpoint)),
            std::make_move_iterator(node.values.end())
        );
        node.keys.erase(node.keys.begin() + static_cast<std::ptrdiff_t>(midpoint), node.keys.end());
        node.values.erase(node.values.begin() + static_cast<std::ptrdiff_t>(midpoint), node.values.end());
        right->next = node.next;
        node.next = right.get();
        return Split{right->keys.front(), std::move(right)};
    }

    Split split_internal(Node& node) {
        const std::size_t midpoint = node.keys.size() / 2;
        const Key separator = node.keys[midpoint];
        auto right = std::make_unique<Node>(false);
        right->keys.assign(
            std::make_move_iterator(node.keys.begin() + static_cast<std::ptrdiff_t>(midpoint + 1)),
            std::make_move_iterator(node.keys.end())
        );
        right->children.insert(
            right->children.end(),
            std::make_move_iterator(node.children.begin() + static_cast<std::ptrdiff_t>(midpoint + 1)),
            std::make_move_iterator(node.children.end())
        );
        node.keys.erase(node.keys.begin() + static_cast<std::ptrdiff_t>(midpoint), node.keys.end());
        node.children.erase(node.children.begin() + static_cast<std::ptrdiff_t>(midpoint + 1), node.children.end());
        return Split{separator, std::move(right)};
    }

    [[nodiscard]] const Key* first_key(const Node& node) const noexcept {
        const Node* current = &node;
        while (!current->leaf) {
            if (current->children.empty()) return nullptr;
            current = current->children.front().get();
        }
        return current->keys.empty() ? nullptr : &current->keys.front();
    }

    [[nodiscard]] bool validate_node(const Node& node, bool is_root) const noexcept {
        if (node.keys.size() > MaxKeys) return false;
        for (std::size_t i = 1; i < node.keys.size(); ++i) {
            if (!less_(node.keys[i - 1], node.keys[i])) return false;
        }
        if (node.leaf) {
            if (!node.children.empty() || node.keys.size() != node.values.size()) return false;
            return is_root || !node.keys.empty();
        }
        if (!node.values.empty()) return false;
        if (node.children.size() != node.keys.size() + 1 || node.children.empty()) return false;
        for (std::size_t i = 0; i < node.children.size(); ++i) {
            if (!node.children[i] || !validate_node(*node.children[i], false)) return false;
            if (i > 0) {
                const Key* child_first = first_key(*node.children[i]);
                if (!child_first || !equal_key(node.keys[i - 1], *child_first)) return false;
            }
        }
        return true;
    }
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
