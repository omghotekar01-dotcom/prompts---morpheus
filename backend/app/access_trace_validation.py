from __future__ import annotations

import bisect
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .access_trace import analyze_access_trace
from .models import AccessDistribution


@dataclass(frozen=True)
class SyntheticClassifierCase:
    expected: AccessDistribution
    predicted: AccessDistribution
    seed: int
    sample_count: int
    domain_size: int
    parameter: str

    @property
    def correct(self) -> bool:
        return self.expected == self.predicted

    def as_dict(self) -> dict[str, object]:
        return {
            "expected": self.expected.value,
            "predicted": self.predicted.value,
            "seed": self.seed,
            "sample_count": self.sample_count,
            "domain_size": self.domain_size,
            "parameter": self.parameter,
            "correct": self.correct,
        }


@dataclass(frozen=True)
class SyntheticClassifierEvaluation:
    cases: tuple[SyntheticClassifierCase, ...]
    confusion: dict[str, dict[str, int]]
    per_family_accuracy: dict[str, float]
    overall_accuracy: float
    evidence_state: str = "SYNTHETIC_GENERATOR_CLASSIFICATION_EVALUATION_NOT_REAL_TRACE_VALIDATION"

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "morpheus-access-trace-classifier-synthetic-evaluation-v1",
            "case_count": len(self.cases),
            "confusion": self.confusion,
            "per_family_accuracy": self.per_family_accuracy,
            "overall_accuracy": self.overall_accuracy,
            "misclassifications": [case.as_dict() for case in self.cases if not case.correct],
            "cases": [case.as_dict() for case in self.cases],
            "evidence_state": self.evidence_state,
            "eligible_for_runtime_automatic_promotion": False,
            "truth_boundary": (
                "Accuracy is measured only against MORPHEUS-owned deterministic synthetic generators with known labels. "
                "It is not real-workload validation, statistical model selection, or evidence that the heuristic labels are safe runtime-control inputs."
            ),
        }


def _uniform_trace(rng: random.Random, sample_count: int, domain_size: int) -> list[int]:
    return [rng.randrange(domain_size) for _ in range(sample_count)]


def _sequential_trace(rng: random.Random, sample_count: int, domain_size: int) -> list[int]:
    start = rng.randrange(domain_size)
    return [(start + index) % domain_size for index in range(sample_count)]


def _hotspot_trace(
    rng: random.Random,
    sample_count: int,
    domain_size: int,
    *,
    hotspot_fraction: float,
    hotspot_probability: float,
) -> list[int]:
    hot_size = max(1, min(domain_size, round(domain_size * hotspot_fraction)))
    cold_size = max(0, domain_size - hot_size)
    values: list[int] = []
    for _ in range(sample_count):
        if cold_size == 0 or rng.random() < hotspot_probability:
            values.append(rng.randrange(hot_size))
        else:
            values.append(hot_size + rng.randrange(cold_size))
    return values


def _zipf_trace(
    rng: random.Random,
    sample_count: int,
    domain_size: int,
    *,
    theta: float,
) -> list[int]:
    weights = [1.0 / (rank**theta) for rank in range(1, domain_size + 1)]
    total = sum(weights)
    cumulative: list[float] = []
    running = 0.0
    for weight in weights:
        running += weight / total
        cumulative.append(running)

    values: list[int] = []
    for _ in range(sample_count):
        draw = rng.random()
        values.append(bisect.bisect_left(cumulative, draw))
    return values


def _case(
    expected: AccessDistribution,
    trace: Iterable[int],
    *,
    seed: int,
    sample_count: int,
    domain_size: int,
    parameter: str,
) -> SyntheticClassifierCase:
    predicted = analyze_access_trace(trace).suggested_distribution
    return SyntheticClassifierCase(
        expected=expected,
        predicted=predicted,
        seed=seed,
        sample_count=sample_count,
        domain_size=domain_size,
        parameter=parameter,
    )


def evaluate_synthetic_classifier(
    *,
    seeds: Iterable[int] = (17, 1337, 2027),
    sample_counts: Iterable[int] = (1000, 5000),
    domain_sizes: Iterable[int] = (100, 1000),
) -> SyntheticClassifierEvaluation:
    """Measure the current heuristic against labeled synthetic generators.

    The evaluation intentionally includes multiple parameters that may expose
    overlap between labels (for example, a very steep Zipf shape can also look
    hotspot-like). Such confusion is recorded rather than tuned away here.
    """

    seeds_tuple = tuple(int(value) for value in seeds)
    samples_tuple = tuple(int(value) for value in sample_counts)
    domains_tuple = tuple(int(value) for value in domain_sizes)
    if not seeds_tuple:
        raise ValueError("at least one seed is required")
    if any(value < 2 for value in samples_tuple):
        raise ValueError("synthetic sample counts must be at least two")
    if any(value < 4 for value in domains_tuple):
        raise ValueError("synthetic domain sizes must be at least four")

    cases: list[SyntheticClassifierCase] = []
    for seed in seeds_tuple:
        for sample_count in samples_tuple:
            for domain_size in domains_tuple:
                base_seed = seed * 1_000_003 + sample_count * 101 + domain_size

                rng = random.Random(base_seed + 1)
                cases.append(_case(
                    AccessDistribution.UNIFORM,
                    _uniform_trace(rng, sample_count, domain_size),
                    seed=seed,
                    sample_count=sample_count,
                    domain_size=domain_size,
                    parameter="uniform",
                ))

                rng = random.Random(base_seed + 2)
                cases.append(_case(
                    AccessDistribution.SEQUENTIAL,
                    _sequential_trace(rng, sample_count, domain_size),
                    seed=seed,
                    sample_count=sample_count,
                    domain_size=domain_size,
                    parameter="sequential",
                ))

                for hotspot_probability in (0.70, 0.80, 0.90):
                    rng = random.Random(base_seed + int(hotspot_probability * 1000))
                    cases.append(_case(
                        AccessDistribution.HOTSPOT,
                        _hotspot_trace(
                            rng,
                            sample_count,
                            domain_size,
                            hotspot_fraction=0.10,
                            hotspot_probability=hotspot_probability,
                        ),
                        seed=seed,
                        sample_count=sample_count,
                        domain_size=domain_size,
                        parameter=f"hotspot_fraction=0.10,probability={hotspot_probability:.2f}",
                    ))

                for theta in (0.75, 1.00, 1.25, 1.50):
                    rng = random.Random(base_seed + int(theta * 10_000))
                    cases.append(_case(
                        AccessDistribution.ZIPF,
                        _zipf_trace(rng, sample_count, domain_size, theta=theta),
                        seed=seed,
                        sample_count=sample_count,
                        domain_size=domain_size,
                        parameter=f"theta={theta:.2f}",
                    ))

    labels = [distribution.value for distribution in AccessDistribution]
    confusion = {expected: {predicted: 0 for predicted in labels} for expected in labels}
    totals: dict[str, int] = defaultdict(int)
    correct: dict[str, int] = defaultdict(int)
    for case in cases:
        expected = case.expected.value
        predicted = case.predicted.value
        confusion[expected][predicted] += 1
        totals[expected] += 1
        if case.correct:
            correct[expected] += 1

    per_family_accuracy = {
        label: round(correct[label] / totals[label], 8) if totals[label] else 0.0
        for label in labels
    }
    overall = sum(1 for case in cases if case.correct) / len(cases)
    return SyntheticClassifierEvaluation(
        cases=tuple(cases),
        confusion=confusion,
        per_family_accuracy=per_family_accuracy,
        overall_accuracy=round(overall, 8),
    )
