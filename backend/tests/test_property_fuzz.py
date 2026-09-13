from __future__ import annotations

from app.models import QueryKind
from app.property_fuzz import (
    FUZZ_EVIDENCE_STATE,
    FUZZ_SCHEMA,
    generate_fuzz_workload,
    run_property_fuzz_campaign,
)


def test_fuzz_generator_reaches_every_query_family_with_replayable_seeds() -> None:
    covered = set()
    for seed in range(len(QueryKind)):
        spec = generate_fuzz_workload(seed)
        covered.update(query.kind for query in spec.queries)
        assert spec.name == f"property_fuzz_{seed}"
        assert generate_fuzz_workload(seed).model_dump(mode="json") == spec.model_dump(mode="json")
    assert covered == set(QueryKind)


def test_property_fuzz_campaign_is_deterministic_and_passes_core_invariants() -> None:
    first = run_property_fuzz_campaign(cases=16, seed=424242, max_candidates=96, beam_width=24)
    second = run_property_fuzz_campaign(cases=16, seed=424242, max_candidates=96, beam_width=24)

    assert first == second
    assert first["schema"] == FUZZ_SCHEMA
    assert first["evidence_state"] == FUZZ_EVIDENCE_STATE
    assert first["success"] is True, first["failures"]
    assert first["cases_requested"] == 16
    assert first["cases_passed"] == 16
    assert len(first["case_seeds"]) == 16
    assert first["invariant_checks"] > 16 * 10
    assert first["failures"] == []
    assert "not end-to-end benchmark evidence" in first["truth_boundary"]


def test_property_fuzz_campaign_records_replay_seed_on_failure(monkeypatch) -> None:
    import app.property_fuzz as property_fuzz

    def fail_case(*args, **kwargs):
        del args, kwargs
        raise AssertionError("synthetic invariant failure")

    monkeypatch.setattr(property_fuzz, "_assert_case_invariants", fail_case)
    report = run_property_fuzz_campaign(cases=2, seed=7)

    assert report["success"] is False
    assert report["cases_passed"] == 0
    assert len(report["failures"]) == 2
    assert all(item["case_seed"] in report["case_seeds"] for item in report["failures"])
    assert all(item["invariant"] == "AssertionError" for item in report["failures"])
