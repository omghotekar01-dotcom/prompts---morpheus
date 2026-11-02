#include "morpheus/empirical_cost_model.hpp"
#include <cmath>
#include <stdexcept>
#include <vector>

#define REQUIRE(condition) do { if (!(condition)) throw std::runtime_error("empirical model test: " #condition); } while(false)

int main() {
    using morpheus::empirical::Observation;
    using morpheus::empirical::CostModel;
    std::vector<Observation> samples;
    // Synthetic deterministic unit-test fixture ONLY; not research benchmark evidence.
    for (int i = 0; i < 48; ++i) {
        Observation row{"robin_hood_hash", "point_lookup", 1000.0 + i * 300,
            500.0 + i * 170, 0.01 + (i % 8) * 0.05, 3.0 + (i % 7) * 4.0, 0};
        row.measured_latency_us = 0.03 + 0.025 * std::log2(row.records + 1) +
            0.04 * std::log2(row.cardinality + 1) + 0.2 * row.selectivity +
            0.01 * std::log1p(row.updates_per_second);
        samples.push_back(row);
    }
    CostModel model;
    model.fit(samples);
    REQUIRE(model.has_model("robin_hood_hash", "point_lookup"));
    REQUIRE(!model.has_model("bitmap", "point_lookup"));
    auto fit = model.predict(samples[20]);
    REQUIRE(std::abs(fit.latency_us - samples[20].measured_latency_us) < 0.001);
    REQUIRE(fit.training_samples == samples.size());
    REQUIRE(fit.training_rmse_us < 0.001);
    bool refused = false;
    try {
        auto unknown = samples[20];
        unknown.primitive = "unregistered";
        (void)model.predict(unknown);
    } catch (const std::out_of_range&) { refused = true; }
    REQUIRE(refused);
    refused = false;
    try {
        auto outside = samples[20];
        outside.records = 1000000000;
        (void)model.predict(outside);
    } catch (const std::out_of_range&) { refused = true; }
    REQUIRE(refused);
    refused = false;
    try {
        auto invalid = samples[20];
        invalid.selectivity = 2;
        (void)model.predict(invalid);
    } catch (const std::invalid_argument&) { refused = true; }
    REQUIRE(refused);
    CostModel empty;
    empty.fit({samples[0]});
    REQUIRE(!empty.has_model("robin_hood_hash", "point_lookup"));
    return 0;
}
