#include "morpheus/native_capabilities.hpp"
#include <cstddef>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

int main() {
    try {
        std::string magic;
        std::size_t rows = 0, count = 0;
        if (!(std::cin >> magic >> rows >> count) ||
            magic != "MORPHEUS_CAPABILITIES_V1" ||
            rows < 1 || count < 1 || count > 32)
            throw std::invalid_argument("invalid capability protocol header");
        std::vector<morpheus::capability::Request> requests;
        for (std::size_t i = 0; i < count; ++i) {
            morpheus::capability::Request r;
            r.rows = rows;
            if (!(std::cin >> r.operation >> r.field_type >> r.cardinality))
                throw std::invalid_argument("invalid capability query");
            if (r.field_type == "-") r.field_type.clear();
            requests.push_back(std::move(r));
        }
        std::string trailing;
        if (std::cin >> trailing) throw std::invalid_argument("unexpected trailing input");
        // Validate the entire request before emitting a success header.
        for (const auto& request : requests)
            for (const auto& primitive : morpheus::capability::implemented)
                (void)morpheus::capability::check(primitive, request);
        std::cout << "OK " << count << " " << morpheus::capability::implemented.size() << "\n";
        for (std::size_t i = 0; i < requests.size(); ++i)
            for (const auto& primitive : morpheus::capability::implemented)
                std::cout << "R " << i << " " << primitive.name << " "
                          << morpheus::capability::verdict_name(morpheus::capability::check(primitive, requests[i]))
                          << "\n";
    } catch (const std::exception& error) {
        std::cerr << "MORPHEUS native capability error: " << error.what() << "\n";
        return 2;
    }
    return 0;
}
