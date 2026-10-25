#include "morpheus/csv_profile.hpp"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <stdexcept>
#include <string>

using morpheus::csv_profile::profile;

int main() {
    const auto real = profile(
        "id,city,temperature\r\n"
        "1,Pune,24.5\r\n"
        "2,Pune,25\r\n"
        "3,Mumbai,25.0\r\n"
    );
    assert(real.record_count == 3);
    assert(real.columns.size() == 3);
    assert(real.columns[0].type == "uint64");
    assert(real.columns[0].distinct_values == 3);
    assert(real.columns[1].type == "string");
    assert(real.columns[1].distinct_values == 2);
    assert(real.columns[2].type == "double");

    const auto different = profile("id,city\n9,Hyderabad\n9,Hyderabad\n10,Nagpur\n");
    assert(different.record_count == 3);
    assert(different.columns[0].distinct_values == 2);
    assert(different.columns[1].distinct_values == 2);

    const auto quoted = profile("id,description\n1,\"Hello, world\"\n2,\"two\\\"quotes\"\n");
    assert(quoted.record_count == 2);

    bool rejected_duplicate = false;
    try { (void)profile("id,id\n1,2\n"); }
    catch (const std::invalid_argument&) { rejected_duplicate = true; }
    assert(rejected_duplicate);

    bool rejected_malformed = false;
    try { (void)profile("id,city\n1,Pune\n2\n"); }
    catch (const std::invalid_argument&) { rejected_malformed = true; }
    assert(rejected_malformed);

    bool rejected_empty = false;
    try { (void)profile("id\n"); }
    catch (const std::invalid_argument&) { rejected_empty = true; }
    assert(rejected_empty);
}
