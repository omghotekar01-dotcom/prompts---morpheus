package com.morpheus.dsa;

/** No external test framework needed: compile and run with stock javac/java. */
public final class PlanScorerSelfTest {
    private static void check(boolean result, String message) {
        if (!result) throw new AssertionError(message);
    }

    private static void close(double actual, double expected, double tolerance) {
        check(Math.abs(actual - expected) <= tolerance,
              "expected " + expected + " but got " + actual);
    }

    public static void main(String[] args) {
        var budget = new PlanScorer.Limits(0.15, 1.0, 2.0, 100.0);
        var weights = new PlanScorer.Weights(1.0, 0.15, 0.20, 0.05);
        var quick = new PlanScorer.Metrics(0.09, 0.10, 1.0, 0.17);
        var bulky = new PlanScorer.Metrics(0.05, 0.20, 1.0, 0.17);
        var result = PlanScorer.evaluate(quick, budget, weights);
        check(result.rejectedBy() == 0, "feasible candidate rejected");
        close(result.value(),
              0.09 + 0.15 * 0.10 / 0.15 + 0.20 * 0.17 * Math.log10(101) + 0.05 / 2,
              1e-12);
        check((PlanScorer.evaluate(bulky, budget, weights).rejectedBy()
                & PlanScorer.MEMORY_LIMIT) != 0, "hard memory budget ignored");
        var expensive = new PlanScorer.Metrics(2.0, 0.2, 3.0, 0.17);
        check(PlanScorer.evaluate(expensive, budget, weights).rejectedBy() == 7,
              "all hard constraints must be independently enforced");
        var relaxed = new PlanScorer.Limits(-1, -1, -1, 0);
        check(PlanScorer.evaluate(expensive, relaxed, weights).rejectedBy() == 0,
              "unset budget must not exclude candidate");
        check(PlanScorer.evaluate(quick, new PlanScorer.Limits(0.15, 1, 2, 0), weights)
                .value() < result.value(), "update-rate must change model score");

        boolean refused = false;
        try {
            new PlanScorer.Metrics(Double.NaN, 0.0, 0.0, 0.0);
        } catch (IllegalArgumentException expected) {
            refused = true;
        }
        check(refused, "nonfinite inputs must fail closed");
        System.out.println("JAVA_PLAN_SCORER_TESTS_PASS");
    }
}
