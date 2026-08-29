from __future__ import annotations

from app.engine import _prediction_source


def test_prediction_source_remains_bootstrap_without_any_calibrated_child() -> None:
    assert _prediction_source(["BOOTSTRAP_PRIOR", "BOOTSTRAP_PRIOR"]) == "BOOTSTRAP_PRIOR"


def test_prediction_source_marks_partially_calibrated_candidate_as_mixed() -> None:
    result = _prediction_source(
        [
            "CALIBRATED:lab:morpheus.RobinHoodHashIndex.v1:n=1000:dist=uniform",
            "BOOTSTRAP_PRIOR",
        ]
    )
    assert result.startswith("MIXED_CALIBRATED_BOOTSTRAP:")
    assert "lab:morpheus.RobinHoodHashIndex.v1:n=1000:dist=uniform" in result


def test_prediction_source_does_not_erase_mixed_mutation_child() -> None:
    result = _prediction_source(
        [
            "MIXED_CALIBRATED_BOOTSTRAP_MUTATION:CALIBRATED:lab:impl:n=1000:dist=hotspot(f=0.1,p=0.8),BOOTSTRAP_PRIOR",
            "BOOTSTRAP_PRIOR",
        ]
    )
    assert result.startswith("MIXED_CALIBRATED_BOOTSTRAP:")
    assert "partial@" in result
    assert result != "BOOTSTRAP_PRIOR"


def test_fully_calibrated_mutation_mix_is_compacted_but_remains_fully_calibrated() -> None:
    child = (
        "CALIBRATED:MUTATION_MIX:"
        "CALIBRATED:lab:impl:n=1000:dist=hotspot(f=0.1,p=0.8),"
        "CALIBRATED:lab:impl:n=1000:dist=sequential"
    )
    result = _prediction_source([child])
    assert result.startswith("CALIBRATED_ANCHORED_MODEL:")
    assert "mutation-mix@" in result
    assert len(result) < len(child)


def test_mixed_child_can_never_promote_candidate_to_fully_calibrated() -> None:
    result = _prediction_source(
        [
            "CALIBRATED:lab:impl:n=1000:dist=uniform",
            "MIXED_CALIBRATED_BOOTSTRAP_MUTATION:CALIBRATED:lab:impl:n=1000:dist=uniform,BOOTSTRAP_PRIOR",
        ]
    )
    assert result.startswith("MIXED_CALIBRATED_BOOTSTRAP:")
    assert not result.startswith("CALIBRATED_ANCHORED_MODEL:")
