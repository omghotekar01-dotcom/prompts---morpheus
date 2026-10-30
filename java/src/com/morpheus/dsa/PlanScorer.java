package com.morpheus.dsa;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/**
 * Deterministic, candidate-specific physical-plan constraints and objective scoring.
 *
 * Every metric comes from the caller's current workload/registered physical
 * implementation estimates, never from a field-name or domain lookup table.
 * This is model evaluation, NOT a benchmark of the submitted dataset.
 *
 * A deliberately small versioned text protocol keeps this runnable with a
 * standard Java 17+ runtime and no JSON library or Python numerical engine.
 */
public final class PlanScorer {
    public static final String PROTOCOL = "MORPHEUS_JAVA_SCORE_V1";
    public static final int MEMORY_LIMIT = 1;
    public static final int LATENCY_LIMIT = 2;
    public static final int BUILD_LIMIT = 4;

    private PlanScorer() { }

    public record Limits(double memoryMB, double latencyUS, double buildMS, double updatesPerSecond) {
        public Limits {
            if (!isLimit(memoryMB) || !isLimit(latencyUS) || !isLimit(buildMS)
                    || !Double.isFinite(updatesPerSecond) || updatesPerSecond < 0) {
                throw new IllegalArgumentException("invalid constraint or update frequency");
            }
        }
    }

    public record Weights(double latency, double memory, double update, double build) {
        public Weights {
            if (!finiteNonnegative(latency) || !finiteNonnegative(memory)
                    || !finiteNonnegative(update) || !finiteNonnegative(build)
                    || latency + memory + update + build <= 0) {
                throw new IllegalArgumentException("objective weights must be finite and nonnegative, with positive sum");
            }
        }
    }

    public record Metrics(double latencyUS, double memoryMB, double buildMS, double updateUS) {
        public Metrics {
            if (!finiteNonnegative(latencyUS) || !finiteNonnegative(memoryMB)
                    || !finiteNonnegative(buildMS) || !finiteNonnegative(updateUS)) {
                throw new IllegalArgumentException("predicted candidate metrics must be finite and nonnegative");
            }
        }
    }

    public record Score(double value, int rejectedBy) { }

    private static boolean finiteNonnegative(double value) {
        return Double.isFinite(value) && value >= 0;
    }

    private static boolean isLimit(double value) {
        return Double.isFinite(value) && (value == -1.0 || value > 0);
    }

    public static Score evaluate(Metrics metrics, Limits limits, Weights weights) {
        int rejected = 0;
        if (limits.memoryMB() > 0 && metrics.memoryMB() > limits.memoryMB()) rejected |= MEMORY_LIMIT;
        if (limits.latencyUS() > 0 && metrics.latencyUS() > limits.latencyUS()) rejected |= LATENCY_LIMIT;
        if (limits.buildMS() > 0 && metrics.buildMS() > limits.buildMS()) rejected |= BUILD_LIMIT;

        double memoryReference = limits.memoryMB() > 0 ? limits.memoryMB() : Math.max(metrics.memoryMB(), 1.0);
        double buildReference = limits.buildMS() > 0 ? limits.buildMS() : Math.max(metrics.buildMS(), 1.0);
        double updatePressure = Math.log10(1.0 + limits.updatesPerSecond());
        double score = weights.latency() * metrics.latencyUS()
                + weights.memory() * metrics.memoryMB() / memoryReference
                + weights.update() * metrics.updateUS() * updatePressure
                + weights.build() * metrics.buildMS() / buildReference;
        if (!Double.isFinite(score) || score < 0) {
            throw new IllegalArgumentException("non-finite or negative modeled score");
        }
        return new Score(score, rejected);
    }

    private static double[] values(String line, int count, String label) {
        if (line == null) throw new IllegalArgumentException("missing " + label);
        String[] parts = line.trim().split("\\s+");
        if (parts.length != count) throw new IllegalArgumentException("incorrect field count for " + label);
        double[] output = new double[count];
        for (int i = 0; i < count; ++i) {
            output[i] = Double.parseDouble(parts[i]);
        }
        return output;
    }

    private static void run() throws IOException {
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        if (!PROTOCOL.equals(reader.readLine())) throw new IllegalArgumentException("unsupported scoring protocol");
        String countLine = reader.readLine();
        if (countLine == null) throw new IllegalArgumentException("missing candidate count");
        int count = Integer.parseInt(countLine.trim());
        if (count <= 0 || count > 10_000) throw new IllegalArgumentException("candidate count must be 1..10000");

        double[] bounds = values(reader.readLine(), 4, "constraints");
        Limits limits = new Limits(bounds[0], bounds[1], bounds[2], bounds[3]);
        double[] objectives = values(reader.readLine(), 4, "objectives");
        Weights weights = new Weights(objectives[0], objectives[1], objectives[2], objectives[3]);

        // Stage entire output first: invalid late rows must not produce a partial valid-looking response.
        StringBuilder answer = new StringBuilder("OK ").append(count).append('\n');
        for (int i = 0; i < count; ++i) {
            double[] row = values(reader.readLine(), 4, "candidate " + i);
            Score scored = evaluate(new Metrics(row[0], row[1], row[2], row[3]), limits, weights);
            answer.append("R ").append(Double.toString(scored.value()))
                  .append(' ').append(scored.rejectedBy()).append('\n');
        }
        if (reader.readLine() != null) throw new IllegalArgumentException("unexpected trailing candidate data");
        System.out.print(answer);
    }

    public static void main(String[] args) {
        if (args.length != 0) {
            System.err.println("PlanScorer expects its versioned workload on stdin");
            System.exit(2);
        }
        try {
            run();
        } catch (IOException | IllegalArgumentException exception) {
            System.err.println("MORPHEUS Java scorer refused request: " + exception.getMessage());
            System.exit(2);
        }
    }
}
