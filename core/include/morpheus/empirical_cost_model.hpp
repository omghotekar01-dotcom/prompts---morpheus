#pragma once
// Native C++20 ridge cost learner: no guessed benchmark samples, no fixed winner.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace morpheus::empirical {
struct Observation {
    std::string primitive;
    std::string operation;
    double records = 0;
    double cardinality = 0;
    double selectivity = 0;
    double updates_per_second = 0;
    double measured_latency_us = 0;
};
struct Prediction {
    double latency_us = 0;
    double training_rmse_us = 0;
    std::size_t training_samples = 0;
};
class CostModel {
    static constexpr std::size_t dimensions = 5;
    using Vector = std::array<double, dimensions>;
    using Matrix = std::array<Vector, dimensions>;
    struct Fitted {
        Vector coefficient{};
        Vector mean{};
        Vector scale{};
        Vector minimum{};
        Vector maximum{};
        double rmse = 0;
        std::size_t samples = 0;
    };
    std::map<std::pair<std::string, std::string>, Fitted> models_;
    static void validate(const Observation& o, bool training) {
        if (o.primitive.empty() || o.operation.empty() ||
            !std::isfinite(o.records) || o.records <= 0 ||
            !std::isfinite(o.cardinality) || o.cardinality < 0 || o.cardinality > o.records ||
            !std::isfinite(o.selectivity) || o.selectivity < 0 || o.selectivity > 1 ||
            !std::isfinite(o.updates_per_second) || o.updates_per_second < 0 ||
            (training && (!std::isfinite(o.measured_latency_us) || o.measured_latency_us <= 0))) {
            throw std::invalid_argument("invalid cost observation or workload features");
        }
    }
    static Vector features(const Observation& o) {
        return {1.0, std::log2(o.records + 1), std::log2(o.cardinality + 1),
                o.selectivity, std::log1p(o.updates_per_second)};
    }
    static Vector solve(Matrix matrix, Vector target) {
        for (std::size_t pivot = 0; pivot < dimensions; ++pivot) {
            std::size_t best = pivot;
            for (std::size_t row = pivot + 1; row < dimensions; ++row)
                if (std::abs(matrix[row][pivot]) > std::abs(matrix[best][pivot])) best = row;
            if (std::abs(matrix[best][pivot]) < 1e-12)
                throw std::runtime_error("empirical model singular design");
            std::swap(matrix[pivot], matrix[best]);
            std::swap(target[pivot], target[best]);
            double diagonal = matrix[pivot][pivot];
            for (std::size_t col = pivot; col < dimensions; ++col) matrix[pivot][col] /= diagonal;
            target[pivot] /= diagonal;
            for (std::size_t row = 0; row < dimensions; ++row) {
                if (row == pivot) continue;
                double factor = matrix[row][pivot];
                for (std::size_t col = pivot; col < dimensions; ++col)
                    matrix[row][col] -= factor * matrix[pivot][col];
                target[row] -= factor * target[pivot];
            }
        }
        return target;
    }
    static double value(const Fitted& f, const Vector& features) {
        double result = f.coefficient[0];
        for (std::size_t j = 1; j < dimensions; ++j)
            result += f.coefficient[j] * (features[j] - f.mean[j]) / f.scale[j];
        return result;
    }
public:
    void fit(const std::vector<Observation>& samples, double ridge = 1e-6) {
        if (!std::isfinite(ridge) || ridge <= 0) throw std::invalid_argument("invalid ridge");
        std::map<std::pair<std::string, std::string>, std::vector<Observation>> groups;
        for (const auto& sample : samples) {
            validate(sample, true);
            groups[{sample.primitive, sample.operation}].push_back(sample);
        }
        std::map<std::pair<std::string, std::string>, Fitted> trained;
        for (const auto& [key, group] : groups) {
            if (group.size() < 8) continue;
            Fitted model;
            model.samples = group.size();
            model.minimum.fill(std::numeric_limits<double>::infinity());
            model.maximum.fill(-std::numeric_limits<double>::infinity());
            std::vector<Vector> inputs;
            for (const auto& sample : group) {
                const Vector f = features(sample);
                inputs.push_back(f);
                for (std::size_t j = 1; j < dimensions; ++j) {
                    model.minimum[j] = std::min(model.minimum[j], f[j]);
                    model.maximum[j] = std::max(model.maximum[j], f[j]);
                    model.mean[j] += f[j] / static_cast<double>(group.size());
                }
            }
            model.scale.fill(1.0);
            for (std::size_t j = 1; j < dimensions; ++j) {
                double variance = 0;
                for (const auto& input : inputs) variance += std::pow(input[j] - model.mean[j], 2);
                model.scale[j] = std::max(std::sqrt(variance / group.size()), 1e-9);
            }
            Matrix gram{};
            Vector rhs{};
            for (std::size_t i = 0; i < group.size(); ++i) {
                Vector row{1.0};
                for (std::size_t j = 1; j < dimensions; ++j)
                    row[j] = (inputs[i][j] - model.mean[j]) / model.scale[j];
                for (std::size_t j = 0; j < dimensions; ++j) {
                    rhs[j] += row[j] * group[i].measured_latency_us;
                    for (std::size_t k = 0; k < dimensions; ++k) gram[j][k] += row[j] * row[k];
                }
            }
            for (std::size_t j = 1; j < dimensions; ++j) gram[j][j] += ridge;
            model.coefficient = solve(gram, rhs);
            double square_error = 0;
            for (std::size_t i = 0; i < group.size(); ++i) {
                double delta = value(model, inputs[i]) - group[i].measured_latency_us;
                square_error += delta * delta;
            }
            model.rmse = std::sqrt(square_error / group.size());
            trained.emplace(key, model);
        }
        models_ = std::move(trained);
    }
    [[nodiscard]] bool has_model(const std::string& primitive, const std::string& operation) const {
        return models_.contains({primitive, operation});
    }
    [[nodiscard]] Prediction predict(const Observation& query) const {
        validate(query, false);
        const auto it = models_.find({query.primitive, query.operation});
        if (it == models_.end()) throw std::out_of_range("NO_MATCHING_TRAINED_MODEL");
        const Vector f = features(query);
        const auto& model = it->second;
        for (std::size_t j = 1; j < dimensions; ++j)
            if (f[j] < model.minimum[j] - 1e-8 || f[j] > model.maximum[j] + 1e-8)
                throw std::out_of_range("OUTSIDE_MEASURED_FEATURE_RANGE");
        const double prediction = value(model, f);
        if (!std::isfinite(prediction) || prediction <= 0)
            throw std::out_of_range("NONPOSITIVE_MODEL_PREDICTION");
        return {prediction, model.rmse, model.samples};
    }
};
} // namespace morpheus::empirical
