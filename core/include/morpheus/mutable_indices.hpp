#pragma once

#include <algorithm>
#include <cstddef>
#include <limits>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace morpheus {

// Mutable adapters used by generated artifacts that need targeted maintenance.
// They deliberately preserve the observable query semantics of the P2 lab
// primitives while adding explicit erase/remove operations.

template <typename Key, typename Value, typename Less = std::less<Key>>
class MutableSortedArrayIndex {
public:
    void bulk_load(std::vector<std::pair<Key, Value>> rows) {
        std::sort(rows.begin(), rows.end(), [this](const auto& left, const auto& right) {
            return less_(left.first, right.first);
        });
        rows_.clear();
        for (auto& row : rows) insert_or_assign(row.first, row.second);
    }

    void insert_or_assign(const Key& key, const Value& value) {
        auto it = lower_bound(key);
        if (it != rows_.end() && equal_key(it->first, key)) {
            it->second = value;
        } else {
            rows_.insert(it, {key, value});
        }
    }

    bool erase(const Key& key) {
        auto it = lower_bound(key);
        if (it == rows_.end() || !equal_key(it->first, key)) return false;
        rows_.erase(it);
        return true;
    }

    [[nodiscard]] const Value* find(const Key& key) const noexcept {
        const auto it = lower_bound_const(key);
        if (it == rows_.end() || !equal_key(it->first, key)) return nullptr;
        return &it->second;
    }

    [[nodiscard]] std::vector<Value> range(const Key& low, const Key& high) const {
        std::vector<Value> out;
        if (less_(high, low)) return out;
        for (auto it = lower_bound_const(low); it != rows_.end() && !less_(high, it->first); ++it) {
            out.push_back(it->second);
        }
        return out;
    }

    [[nodiscard]] std::size_t size() const noexcept { return rows_.size(); }

private:
    std::vector<std::pair<Key, Value>> rows_;
    Less less_{};

    [[nodiscard]] bool equal_key(const Key& left, const Key& right) const noexcept {
        return !less_(left, right) && !less_(right, left);
    }

    auto lower_bound(const Key& key) {
        return std::lower_bound(rows_.begin(), rows_.end(), key, [this](const auto& row, const Key& value) {
            return less_(row.first, value);
        });
    }

    auto lower_bound_const(const Key& key) const {
        return std::lower_bound(rows_.begin(), rows_.end(), key, [this](const auto& row, const Key& value) {
            return less_(row.first, value);
        });
    }
};


template <typename Value>
class MutablePrefixTrie {
public:
    void insert_or_assign(const std::string& key, const Value& value) {
        Node* node = &root_;
        for (const char ch : key) {
            auto& next = node->children[ch];
            if (!next) next = std::make_unique<Node>();
            node = next.get();
        }
        if (!node->value.has_value()) ++size_;
        node->value = value;
    }

    bool erase(const std::string& key) {
        bool removed = false;
        erase_recursive(root_, key, 0, removed);
        if (removed) --size_;
        return removed;
    }

    [[nodiscard]] const Value* find(const std::string& key) const noexcept {
        const Node* node = descend(key);
        return node && node->value.has_value() ? &node->value.value() : nullptr;
    }

    [[nodiscard]] std::vector<Value> prefix_search(const std::string& prefix, std::size_t limit = 100) const {
        std::vector<Value> out;
        const Node* node = descend(prefix);
        if (!node || limit == 0) return out;
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
        for (const char ch : key) {
            const auto it = node->children.find(ch);
            if (it == node->children.end()) return nullptr;
            node = it->second.get();
        }
        return node;
    }

    static bool erase_recursive(Node& node, const std::string& key, std::size_t depth, bool& removed) {
        if (depth == key.size()) {
            if (!node.value.has_value()) return false;
            node.value.reset();
            removed = true;
        } else {
            const auto it = node.children.find(key[depth]);
            if (it == node.children.end()) return false;
            if (erase_recursive(*it->second, key, depth + 1, removed)) node.children.erase(it);
        }
        return !node.value.has_value() && node.children.empty();
    }

    static void collect(const Node& node, std::vector<Value>& out, std::size_t limit) {
        if (out.size() >= limit) return;
        if (node.value.has_value()) out.push_back(node.value.value());
        if (out.size() >= limit) return;

        std::vector<char> keys;
        keys.reserve(node.children.size());
        for (const auto& [key, unused] : node.children) {
            (void)unused;
            keys.push_back(key);
        }
        std::sort(keys.begin(), keys.end());
        for (const char key : keys) {
            collect(*node.children.at(key), out, limit);
            if (out.size() >= limit) return;
        }
    }
};


// Trie-backed prefix adapter that preserves duplicate logical records.
//
// MutablePrefixTrie intentionally stores one value per exact key. Generated
// record indexes, however, may contain several live records with the same string
// field. This adapter stores a sorted stable-slot posting vector as each trie's
// value. Exact lookup returns the last live slot for backwards-compatible
// point-lookup semantics, while prefix_search flattens every posting so prefix
// queries do not silently drop duplicate records.
template <typename RecordId = std::size_t>
class MutableMultiPrefixTrie {
public:
    void add(const std::string& key, RecordId id) {
        auto& ids = postings_[key];
        const auto position = std::lower_bound(ids.begin(), ids.end(), id);
        if (position == ids.end() || *position != id) ids.insert(position, id);
        trie_.insert_or_assign(key, ids);
    }

    bool remove(const std::string& key, RecordId id) {
        const auto posting = postings_.find(key);
        if (posting == postings_.end()) return false;
        auto& ids = posting->second;
        const auto position = std::lower_bound(ids.begin(), ids.end(), id);
        if (position == ids.end() || *position != id) return false;
        ids.erase(position);
        if (ids.empty()) {
            postings_.erase(posting);
            trie_.erase(key);
        } else {
            trie_.insert_or_assign(key, ids);
        }
        return true;
    }

    [[nodiscard]] const RecordId* find(const std::string& key) const noexcept {
        const auto* ids = trie_.find(key);
        return ids && !ids->empty() ? &ids->back() : nullptr;
    }

    [[nodiscard]] std::vector<RecordId> prefix_search(
        const std::string& prefix,
        std::size_t limit = 100
    ) const {
        std::vector<RecordId> out;
        if (limit == 0) return out;
        const auto groups = trie_.prefix_search(prefix, std::numeric_limits<std::size_t>::max());
        out.reserve(std::min(limit, total_postings(groups)));
        for (const auto& ids : groups) {
            for (const auto id : ids) {
                out.push_back(id);
                if (out.size() >= limit) return out;
            }
        }
        return out;
    }

    [[nodiscard]] std::size_t key_count() const noexcept { return postings_.size(); }

private:
    MutablePrefixTrie<std::vector<RecordId>> trie_;
    std::unordered_map<std::string, std::vector<RecordId>> postings_;

    static std::size_t total_postings(const std::vector<std::vector<RecordId>>& groups) noexcept {
        std::size_t total = 0;
        for (const auto& group : groups) total += group.size();
        return total;
    }
};


template <typename Category, typename RecordId = std::size_t>
class MutableBitmapFilterIndex {
public:
    void add(const Category& category, RecordId id) {
        auto& ids = postings_[category];
        const auto it = std::lower_bound(ids.begin(), ids.end(), id);
        if (it == ids.end() || *it != id) ids.insert(it, id);
    }

    bool remove(const Category& category, RecordId id) {
        const auto posting = postings_.find(category);
        if (posting == postings_.end()) return false;
        auto& ids = posting->second;
        const auto it = std::lower_bound(ids.begin(), ids.end(), id);
        if (it == ids.end() || *it != id) return false;
        ids.erase(it);
        if (ids.empty()) postings_.erase(posting);
        return true;
    }

    [[nodiscard]] std::vector<RecordId> filter(const Category& category) const {
        const auto it = postings_.find(category);
        return it == postings_.end() ? std::vector<RecordId>{} : it->second;
    }

    [[nodiscard]] std::size_t category_count() const noexcept { return postings_.size(); }

private:
    std::unordered_map<Category, std::vector<RecordId>> postings_;
};

} // namespace morpheus