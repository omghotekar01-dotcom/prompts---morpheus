#pragma once

#include <algorithm>
#include <cstddef>
#include <functional>
#include <iterator>
#include <memory>
#include <optional>
#include <utility>
#include <vector>

namespace morpheus {

// B+ tree primitive with incremental deletion.
//
// Internal separator keys are derived from the first key of each right child.
// Deletion rebalances locally by borrowing/merging children and can collapse
// the root, avoiding the full-tree rebuild used by the legacy OrderedTreeIndex.
template <typename Key, typename Value, std::size_t MaxKeys = 31, typename Less = std::less<Key>>
class BPlusTreeIndex {
    static_assert(MaxKeys >= 3, "B+ tree MaxKeys must be at least 3");

public:
    BPlusTreeIndex() : root_(std::make_unique<Node>(true)) {}

    void insert_or_assign(const Key& key, const Value& value) {
        auto split = insert_recursive(*root_, key, value);
        if (!split.has_value()) return;

        auto new_root = std::make_unique<Node>(false);
        new_root->children.push_back(std::move(root_));
        new_root->children.push_back(std::move(split->right));
        rebuild_separators(*new_root);
        root_ = std::move(new_root);
    }

    bool erase(const Key& key) {
        std::vector<PathEntry> path;
        Node* leaf = find_leaf_mutable(key, path);
        if (!leaf) return false;
        const auto it = std::lower_bound(leaf->keys.begin(), leaf->keys.end(), key, less_);
        if (it == leaf->keys.end() || !equal_key(*it, key)) return false;

        const auto index = static_cast<std::size_t>(std::distance(leaf->keys.begin(), it));
        leaf->keys.erase(it);
        leaf->values.erase(leaf->values.begin() + static_cast<std::ptrdiff_t>(index));
        --size_;

        Node* current = leaf;
        for (std::size_t depth = path.size(); depth > 0; --depth) {
            Node* parent = path[depth - 1].parent;
            std::size_t child_index = path[depth - 1].child_index;

            if (underflow(*current)) {
                child_index = rebalance_child(*parent, child_index);
                current = parent->children.at(child_index).get();
            }
            rebuild_separators(*parent);
            current = parent;
        }

        while (!root_->leaf && root_->children.size() == 1) {
            root_ = std::move(root_->children.front());
        }
        if (size_ == 0 && !root_->leaf) root_ = std::make_unique<Node>(true);
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
                begin = static_cast<std::size_t>(std::distance(
                    leaf->keys.begin(), std::lower_bound(leaf->keys.begin(), leaf->keys.end(), low, less_)
                ));
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
    [[nodiscard]] bool empty() const noexcept { return size_ == 0; }

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
            for (std::size_t i = 0; i < leaf->keys.size(); ++i) out.emplace_back(leaf->keys[i], leaf->values[i]);
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
        std::unique_ptr<Node> right;
    };

    struct PathEntry {
        Node* parent;
        std::size_t child_index;
    };

    std::unique_ptr<Node> root_;
    std::size_t size_ = 0;
    Less less_{};

    static constexpr std::size_t min_leaf_keys() noexcept {
        return (MaxKeys + 1U) / 2U;
    }

    static constexpr std::size_t min_internal_children() noexcept {
        return (MaxKeys + 2U) / 2U;
    }

    [[nodiscard]] bool equal_key(const Key& left, const Key& right) const noexcept {
        return !less_(left, right) && !less_(right, left);
    }

    [[nodiscard]] bool underflow(const Node& node) const noexcept {
        return node.leaf ? node.keys.size() < min_leaf_keys() : node.children.size() < min_internal_children();
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

    Node* find_leaf_mutable(const Key& key, std::vector<PathEntry>& path) noexcept {
        Node* node = root_.get();
        while (node && !node->leaf) {
            const auto it = std::upper_bound(node->keys.begin(), node->keys.end(), key, less_);
            const auto child_index = static_cast<std::size_t>(std::distance(node->keys.begin(), it));
            if (child_index >= node->children.size()) return nullptr;
            path.push_back({node, child_index});
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
        if (!child_split.has_value()) {
            rebuild_separators(node);
            return std::nullopt;
        }

        node.children.insert(
            node.children.begin() + static_cast<std::ptrdiff_t>(child_index + 1), std::move(child_split->right)
        );
        rebuild_separators(node);
        if (node.keys.size() <= MaxKeys) return std::nullopt;
        return split_internal(node);
    }

    Split split_leaf(Node& node) {
        const std::size_t midpoint = node.keys.size() / 2U;
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
        return Split{std::move(right)};
    }

    Split split_internal(Node& node) {
        const std::size_t left_children = (node.children.size() + 1U) / 2U;
        auto right = std::make_unique<Node>(false);
        right->children.insert(
            right->children.end(),
            std::make_move_iterator(node.children.begin() + static_cast<std::ptrdiff_t>(left_children)),
            std::make_move_iterator(node.children.end())
        );
        node.children.erase(node.children.begin() + static_cast<std::ptrdiff_t>(left_children), node.children.end());
        rebuild_separators(node);
        rebuild_separators(*right);
        return Split{std::move(right)};
    }

    std::size_t rebalance_child(Node& parent, std::size_t child_index) {
        Node& child = *parent.children.at(child_index);
        if (child.leaf) return rebalance_leaf(parent, child_index);
        return rebalance_internal(parent, child_index);
    }

    std::size_t rebalance_leaf(Node& parent, std::size_t child_index) {
        Node& child = *parent.children.at(child_index);

        if (child_index > 0) {
            Node& left = *parent.children[child_index - 1];
            if (left.keys.size() > min_leaf_keys()) {
                child.keys.insert(child.keys.begin(), std::move(left.keys.back()));
                child.values.insert(child.values.begin(), std::move(left.values.back()));
                left.keys.pop_back();
                left.values.pop_back();
                rebuild_separators(parent);
                return child_index;
            }
        }
        if (child_index + 1 < parent.children.size()) {
            Node& right = *parent.children[child_index + 1];
            if (right.keys.size() > min_leaf_keys()) {
                child.keys.push_back(std::move(right.keys.front()));
                child.values.push_back(std::move(right.values.front()));
                right.keys.erase(right.keys.begin());
                right.values.erase(right.values.begin());
                rebuild_separators(parent);
                return child_index;
            }
        }

        if (child_index > 0) {
            Node& left = *parent.children[child_index - 1];
            left.keys.insert(left.keys.end(), std::make_move_iterator(child.keys.begin()), std::make_move_iterator(child.keys.end()));
            left.values.insert(left.values.end(), std::make_move_iterator(child.values.begin()), std::make_move_iterator(child.values.end()));
            left.next = child.next;
            parent.children.erase(parent.children.begin() + static_cast<std::ptrdiff_t>(child_index));
            rebuild_separators(parent);
            return child_index - 1;
        }

        Node& right = *parent.children.at(1);
        child.keys.insert(child.keys.end(), std::make_move_iterator(right.keys.begin()), std::make_move_iterator(right.keys.end()));
        child.values.insert(child.values.end(), std::make_move_iterator(right.values.begin()), std::make_move_iterator(right.values.end()));
        child.next = right.next;
        parent.children.erase(parent.children.begin() + 1);
        rebuild_separators(parent);
        return 0;
    }

    std::size_t rebalance_internal(Node& parent, std::size_t child_index) {
        Node& child = *parent.children.at(child_index);

        if (child_index > 0) {
            Node& left = *parent.children[child_index - 1];
            if (left.children.size() > min_internal_children()) {
                child.children.insert(child.children.begin(), std::move(left.children.back()));
                left.children.pop_back();
                rebuild_separators(left);
                rebuild_separators(child);
                rebuild_separators(parent);
                return child_index;
            }
        }
        if (child_index + 1 < parent.children.size()) {
            Node& right = *parent.children[child_index + 1];
            if (right.children.size() > min_internal_children()) {
                child.children.push_back(std::move(right.children.front()));
                right.children.erase(right.children.begin());
                rebuild_separators(right);
                rebuild_separators(child);
                rebuild_separators(parent);
                return child_index;
            }
        }

        if (child_index > 0) {
            Node& left = *parent.children[child_index - 1];
            left.children.insert(
                left.children.end(), std::make_move_iterator(child.children.begin()), std::make_move_iterator(child.children.end())
            );
            parent.children.erase(parent.children.begin() + static_cast<std::ptrdiff_t>(child_index));
            rebuild_separators(left);
            rebuild_separators(parent);
            return child_index - 1;
        }

        Node& right = *parent.children.at(1);
        child.children.insert(
            child.children.end(), std::make_move_iterator(right.children.begin()), std::make_move_iterator(right.children.end())
        );
        parent.children.erase(parent.children.begin() + 1);
        rebuild_separators(child);
        rebuild_separators(parent);
        return 0;
    }

    void rebuild_separators(Node& node) {
        if (node.leaf) return;
        node.keys.clear();
        if (node.children.size() < 2) return;
        node.keys.reserve(node.children.size() - 1);
        for (std::size_t i = 1; i < node.children.size(); ++i) {
            const Key* key = first_key(*node.children[i]);
            if (key) node.keys.push_back(*key);
        }
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
        if (node.leaf) {
            if (!node.children.empty() || node.keys.size() != node.values.size() || node.keys.size() > MaxKeys) return false;
            if (!is_root && node.keys.size() < min_leaf_keys()) return false;
            for (std::size_t i = 1; i < node.keys.size(); ++i) {
                if (!less_(node.keys[i - 1], node.keys[i])) return false;
            }
            return is_root || !node.keys.empty();
        }

        if (!node.values.empty() || node.children.size() != node.keys.size() + 1 || node.keys.size() > MaxKeys) return false;
        if (is_root) {
            if (node.children.size() < 2) return false;
        } else if (node.children.size() < min_internal_children()) {
            return false;
        }
        for (std::size_t i = 0; i < node.children.size(); ++i) {
            if (!node.children[i] || !validate_node(*node.children[i], false)) return false;
            if (i > 0) {
                const Key* child_first = first_key(*node.children[i]);
                if (!child_first || !equal_key(node.keys[i - 1], *child_first)) return false;
            }
        }
        for (std::size_t i = 1; i < node.keys.size(); ++i) {
            if (!less_(node.keys[i - 1], node.keys[i])) return false;
        }
        return true;
    }
};

} // namespace morpheus
