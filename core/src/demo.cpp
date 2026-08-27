#include "morpheus/structures.hpp"

#include <cstdint>
#include <iostream>
#include <string>

int main() {
    morpheus::RobinHoodHashIndex<std::uint64_t, std::string> users;
    users.insert_or_assign(1, "Ada");
    users.insert_or_assign(2, "Grace");

    if (const auto* name = users.find(2)) {
        std::cout << "MORPHEUS core demo lookup: " << *name << '\n';
    }

    morpheus::OrderedTreeIndex<int, std::string> by_age;
    by_age.insert_or_assign(21, "user-1");
    by_age.insert_or_assign(28, "user-2");
    by_age.insert_or_assign(35, "user-3");
    std::cout << "Range result count [20,30]: " << by_age.range(20, 30).size() << '\n';
    return 0;
}
