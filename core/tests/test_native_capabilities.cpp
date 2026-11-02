#include "morpheus/native_capabilities.hpp"
#include <stdexcept>
#include <string>

#define REQUIRE(x) do { if (!(x)) throw std::runtime_error("capability test failure: " #x); } while(false)
int main() {
    using namespace morpheus::capability;
    Request point{1000,"point_lookup","string",1000};
    REQUIRE(check(implemented[0], point) == Verdict::eligible);
    REQUIRE(check(implemented[4], point) == Verdict::unsupported_operation);
    Request prefix{1000,"prefix_search","string",98};
    REQUIRE(check(implemented[3], prefix) == Verdict::eligible);
    prefix.field_type = "uint64";
    REQUIRE(check(implemented[3], prefix) == Verdict::incompatible_type);
    Request filter{1000000,"filter","string",500000};
    REQUIRE(check(implemented[4], filter) == Verdict::excessive_cardinality);
    filter.cardinality = 5;
    REQUIRE(check(implemented[4], filter) == Verdict::eligible);
    Request graph{1000,"graph_traversal","",0};
    REQUIRE(check(implemented[5], graph) == Verdict::eligible);
    REQUIRE(check(implemented[0], graph) == Verdict::unsupported_operation);
    return 0;
}
