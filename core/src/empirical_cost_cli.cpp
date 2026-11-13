#include "morpheus/empirical_cost_model.hpp"
#include <cstddef>
#include <exception>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
morpheus::empirical::Observation read_row(bool measured) {
    morpheus::empirical::Observation o;
    if (!(std::cin >> o.primitive >> o.operation >> o.records >> o.cardinality
          >> o.selectivity >> o.updates_per_second))
        throw std::invalid_argument("invalid observation features");
    if (measured && !(std::cin >> o.measured_latency_us))
        throw std::invalid_argument("missing measured latency");
    return o;
}
}
int main() {
    try {
        std::string magic;
        std::size_t sample_count = 0;
        if (!(std::cin >> magic >> sample_count) ||
            magic != "MORPHEUS_EMPIRICAL_COST_V1" || sample_count == 0 ||
            sample_count > 100000)
            throw std::invalid_argument("invalid protocol or sample count");
        std::vector<morpheus::empirical::Observation> samples;
        samples.reserve(sample_count);
        for (std::size_t i = 0; i < sample_count; ++i) samples.push_back(read_row(true));
        morpheus::empirical::CostModel model;
        model.fit(samples);
        std::size_t count = 0;
        if (!(std::cin >> count) || count > 10000)
            throw std::invalid_argument("invalid prediction count");
        std::vector<morpheus::empirical::Observation> requests;
        for (std::size_t i = 0; i < count; ++i) requests.push_back(read_row(false));
        std::string extra;
        if (std::cin >> extra) throw std::invalid_argument("unexpected trailing input");
        std::cout << std::setprecision(17) << "OK " << requests.size() << "\n";
        for (const auto& request : requests) {
            try {
                auto predicted = model.predict(request);
                std::cout << "P " << predicted.latency_us << " " << predicted.training_rmse_us
                          << " " << predicted.training_samples << "\n";
            } catch (const std::out_of_range& unavailable) {
                std::cout << "U " << unavailable.what() << "\n";
            }
        }
    } catch (const std::exception& error) {
        std::cerr << "MORPHEUS native empirical model error: " << error.what() << "\n";
        return 2;
    }
    return 0;
}
