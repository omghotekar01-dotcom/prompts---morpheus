# MASTER PROMPT #3 — V01: PROBLEM, VISION & SCIENTIFIC FOUNDATIONS

Establish the technical motivation and research framing of MORPHEUS before implementation.

## Problem
Application performance depends strongly on physical data representation, yet developers often choose structures manually using asymptotic rules or habit. Real workloads are mixed, hardware-sensitive and constrained by memory/update/build costs. One structure rarely dominates all operations.

## Vision
Treat physical representation as a search problem. Given dataset D, workload W, hardware H, primitive library P, constraints R and objectives O, MORPHEUS identifies a feasible configuration C, generates executable implementation, verifies it and measures it.

## Key ideas to investigate
- heterogeneous composition can outperform one general-purpose structure;
- machine-calibrated empirical models can improve structure ranking;
- model-guided search can approach exhaustive optimum with fewer evaluations;
- explicit transition cost can make runtime adaptation rational rather than reactive;
- reproducible workload specification can turn performance design into a versioned engineering artifact.

## Scientific boundaries
Initial scope may be single-node, in-memory, single-threaded, record-oriented and finite primitive library. State these assumptions rather than pretending to solve distributed databases. Expand scope only with new evidence/testing.

## Core research questions
Can MORPHEUS beat strong fixed/manual baselines under mixed workloads? How close is search to empirical optimum? How accurate is cost ranking across machines? Which mechanisms create gains? When is adaptation worth its switching cost?

## Evaluation principles
Use controlled synthetic workloads plus realistic traces when available. Sweep N, operation mix, cardinality, selectivity, skew and update ratio. Compare absolute metrics and effect sizes, not only percentages. Preserve negative cases where simple structures win.

## Target contribution hierarchy
1. Formal workload/physical-design abstraction.
2. Extensible capability-based composition space.
3. Hardware-aware empirical cost prediction.
4. Constrained multi-objective synthesis/search.
5. Correct executable generation.
6. Transition-aware adaptation.
7. Reproducible evidence/provenance.

## Deliverable
Produce motivation, scope, assumptions, hypotheses, RQs, evaluation criteria, terminology and a contribution ledger that later volumes can refine. Do not write novelty claims as facts before prior-art review.

# END MASTER PROMPT #3
