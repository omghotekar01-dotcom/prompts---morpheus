from __future__ import annotations

import json
from pathlib import Path

from app.research_suite import freeze_experiment_matrix


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_DIR = REPO_ROOT / "research" / "matrices"
EXPECTED_STUDIES = {
    "rq1-end-to-end-v1",
    "rq2-cost-model-v1",
    "rq3-search-quality-v1",
    "rq4-composition-v1",
    "rq5-adaptation-v1",
    "rq6-robustness-v1",
    "rq7-generated-migration-v1",
}


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_frozen_research_matrices_expand_deterministically_within_declared_budget() -> None:
    paths = sorted(MATRIX_DIR.glob("*.json"))
    assert paths, "research matrix directory is empty"

    observed_studies: set[str] = set()
    for path in paths:
        payload = _load(path)
        study_id = str(payload["study_id"])
        observed_studies.add(study_id)
        first = freeze_experiment_matrix(
            study_id=study_id,
            hypothesis=str(payload["hypothesis"]),
            metric=str(payload["metric"]),
            lower_is_better=bool(payload["lower_is_better"]),
            repetitions=int(payload["repetitions"]),
            seeds=[int(seed) for seed in payload["seeds"]],
            axes=payload["axes"],
            max_experiments=int(payload["max_experiments"]),
        )
        second = freeze_experiment_matrix(
            study_id=study_id,
            hypothesis=str(payload["hypothesis"]),
            metric=str(payload["metric"]),
            lower_is_better=bool(payload["lower_is_better"]),
            repetitions=int(payload["repetitions"]),
            seeds=[int(seed) for seed in payload["seeds"]],
            axes=dict(reversed(list(payload["axes"].items()))),
            max_experiments=int(payload["max_experiments"]),
        )

        assert first.manifest_sha256 == second.manifest_sha256, path.name
        assert len(first.experiments) <= int(payload["max_experiments"]), path.name
        assert len({item.experiment_id for item in first.experiments}) == len(first.experiments), path.name
        assert all(item.evidence_state == "FROZEN_EXPERIMENT_PLAN_NOT_EXECUTED" for item in first.experiments)

    assert EXPECTED_STUDIES <= observed_studies


def test_rq7_generated_migration_matrix_uses_explicit_deterministic_seed_identity() -> None:
    payload = _load(MATRIX_DIR / "rq7-generated-migration.json")
    assert payload["study_id"] == "rq7-generated-migration-v1"
    assert payload["seeds"] == [0]
    assert payload["axes"]["candidate_pair_policy"] == ["winner-to-best-distinct"]
    assert payload["axes"]["readers"] == [1, 4, 16]
    assert payload["axes"]["record_count"] == [128, 1024, 8192, 65536]
    assert payload["axes"]["transitions"] == [10, 100]
    assert "non-randomized" in payload["seed_note"]
    assert "CI-smoke" in payload["execution_note"]
