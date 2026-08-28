#include "morpheus/mutable_indices.hpp"

#include <cassert>
#include <cstddef>
#include <iostream>
#include <string>
#include <vector>

int main() {
    {
        morpheus::MutableSortedArrayIndex<int, std::size_t> index;
        index.insert_or_assign(30, 3);
        index.insert_or_assign(10, 1);
        index.insert_or_assign(20, 2);
        index.insert_or_assign(20, 22);
        assert(index.size() == 3);
        assert(index.find(20) && *index.find(20) == 22);
        assert((index.range(10, 20) == std::vector<std::size_t>{1, 22}));
        assert(index.erase(20));
        assert(!index.erase(20));
        assert(index.find(20) == nullptr);
        assert(index.size() == 2);
    }

    {
        morpheus::MutablePrefixTrie<std::size_t> trie;
        trie.insert_or_assign("app", 1);
        trie.insert_or_assign("apple", 2);
        trie.insert_or_assign("apt", 3);
        trie.insert_or_assign("bat", 4);
        trie.insert_or_assign("app", 11);
        assert(trie.size() == 4);
        assert(trie.find("app") && *trie.find("app") == 11);
        assert((trie.prefix_search("ap") == std::vector<std::size_t>{11, 2, 3}));
        assert(trie.erase("app"));
        assert(trie.find("app") == nullptr);
        assert(trie.find("apple") && *trie.find("apple") == 2);
        assert((trie.prefix_search("ap") == std::vector<std::size_t>{2, 3}));
        assert(!trie.erase("app"));
        assert(trie.erase("apple"));
        assert(trie.erase("apt"));
        assert(trie.prefix_search("ap").empty());
        assert(trie.size() == 1);
    }

    {
        morpheus::MutableMultiPrefixTrie<std::size_t> trie;
        trie.add("app", 9);
        trie.add("app", 2);
        trie.add("apple", 5);
        trie.add("apt", 7);
        trie.add("bat", 11);
        trie.add("app", 2);  // duplicate slot insertion is idempotent

        assert(trie.key_count() == 4);
        assert(trie.find("app") && *trie.find("app") == 9);
        assert((trie.prefix_search("ap") == std::vector<std::size_t>{2, 9, 5, 7}));
        assert((trie.prefix_search("ap", 3) == std::vector<std::size_t>{2, 9, 5}));

        assert(trie.remove("app", 9));
        assert(trie.find("app") && *trie.find("app") == 2);
        assert((trie.prefix_search("app") == std::vector<std::size_t>{2, 5}));
        assert(!trie.remove("app", 9));
        assert(trie.remove("app", 2));
        assert(trie.find("app") == nullptr);
        assert((trie.prefix_search("ap") == std::vector<std::size_t>{5, 7}));
        assert(trie.key_count() == 3);
    }

    {
        morpheus::MutableBitmapFilterIndex<std::string, std::size_t> bitmap;
        bitmap.add("Pune", 9);
        bitmap.add("Pune", 2);
        bitmap.add("Pune", 5);
        bitmap.add("Pune", 5);
        bitmap.add("Nashik", 7);
        assert((bitmap.filter("Pune") == std::vector<std::size_t>{2, 5, 9}));
        assert(bitmap.category_count() == 2);
        assert(bitmap.remove("Pune", 5));
        assert((bitmap.filter("Pune") == std::vector<std::size_t>{2, 9}));
        assert(!bitmap.remove("Pune", 5));
        assert(bitmap.remove("Nashik", 7));
        assert(bitmap.filter("Nashik").empty());
        assert(bitmap.category_count() == 1);
    }

    std::cout << "MORPHEUS mutable generated-index adapter tests passed\n";
    return 0;
}
