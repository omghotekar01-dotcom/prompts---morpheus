import pytest

from app.research_promotion import ResearchPromotionError, verify_research_promotion


def _ledger(*, allowed: bool = False):
    return {
        "schema": "morpheus-distribution-research-readiness-v1",
        "features": [
            {
                "feature": "trace_characterization",
                "automatic_control_allowed": allowed,
                "blocker": "independent validation required",
            },
            {
                "feature": "window_drift",
                "automatic_control_allowed": False,
                "blocker": "external benchmark campaign required",
            },
        ],
    }


def test_blocks_research_only_feature_with_explicit_reason():
    result = verify_research_promotion(_ledger(), requested_features=["trace_characterization"])
    assert result["promoted"] is False
    assert result["decision"] == "RESEARCH_ONLY"
    assert result["blocked_features"] == [
        {"feature": "trace_characterization", "blocker": "independent validation required"}
    ]


def test_allows_only_explicit_boolean_authorization():
    result = verify_research_promotion(_ledger(allowed=True), requested_features=["trace_characterization"])
    assert result["promoted"] is True
    assert result["decision"] == "ALLOW_AUTOMATIC_CONTROL"


@pytest.mark.parametrize("value", [1, 0, "true", None])
def test_rejects_non_boolean_control_authorization(value):
    ledger = _ledger()
    ledger["features"][0]["automatic_control_allowed"] = value
    with pytest.raises(ResearchPromotionError, match="must be boolean"):
        verify_research_promotion(ledger, requested_features=["trace_characterization"])


def test_rejects_unknown_and_duplicate_feature_requests():
    with pytest.raises(ResearchPromotionError, match="unknown research feature"):
        verify_research_promotion(_ledger(), requested_features=["unknown"])
    with pytest.raises(ResearchPromotionError, match="duplicate requested research feature"):
        verify_research_promotion(
            _ledger(), requested_features=["trace_characterization", "trace_characterization"]
        )


def test_rejects_duplicate_ledger_feature_identity():
    ledger = _ledger()
    ledger["features"].append(dict(ledger["features"][0]))
    with pytest.raises(ResearchPromotionError, match="duplicate readiness feature"):
        verify_research_promotion(ledger, requested_features=["trace_characterization"])
