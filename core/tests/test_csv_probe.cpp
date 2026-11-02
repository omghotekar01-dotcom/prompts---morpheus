#include "morpheus/csv_probe.hpp"

#include <stdexcept>
#include <string>

static void check(bool good, const char* msg) {
    if (!good) throw std::runtime_error(msg);
}

int main() {
    using morpheus::csv_probe::query;
    const std::string text =
        "id,title,price\n"
        "1,\"Book, new\",100\n"
        "2,Desk,950\n"
        "3,\"Book, new\",125\n"
        "4,Pen,25\n";
    {
        const auto r = query(text, 1, "filter", "Book, new", "", 2);
        check(r.total_rows == 4 && r.matched_count == 2 && r.preview.size() == 2, "duplicate equality");
        check(r.preview[0].index == 1 && r.preview[1].index == 3, "stable original row positions");
        check(r.preview[0].cells[1] == "Book, new", "quoted CSV field decoded");
    }
    {
        const auto r = query(text, 2, "range_scan", "120", "950", 2);
        check(r.matched_count == 2, "numeric range must use numeric, not lexicographic, order");
        check(r.preview[0].index == 2 && r.preview[1].index == 3, "numeric range matching source rows");
    }
    {
        const auto r = query(text, 1, "prefix_search", "Bo", "", 1);
        check(r.matched_count == 2 && r.preview.size() == 1, "prefix count and bounded preview");
    }
    {
        const auto r = query(text, 0, "point_lookup", "3", "", 10);
        check(r.matched_count == 1 && r.preview[0].cells[2] == "125", "exact column lookup");
    }
    {
        const std::string original = "Pune \xE2\x82\xB9 new";
        check(morpheus::csv_probe::hex_decode(morpheus::csv_probe::hex_encode(original)) == original,
              "UTF-8 round trip");
        check(morpheus::csv_probe::hex_decode("-").empty(), "empty cell marker");
    }
    {
        bool rejected = false;
        try { (void)query(text, 2, "range_scan", "1000", "100", 20); }
        catch (const std::invalid_argument&) { rejected = true; }
        check(rejected, "invalid numeric bounds must fail");
    }
    {
        const std::string large_ints =
            "large\n9007199254740992\n9007199254740993\n";
        const auto r = query(large_ints, 0, "filter", "9007199254740993", "", 20);
        check(r.matched_count == 1 && r.preview[0].index == 2,
              "64-bit integer equality must not lose precision");
    }
}
