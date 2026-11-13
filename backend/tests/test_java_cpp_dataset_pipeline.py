from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.csv_profile_api import router
from app.java_plan_scorer import java_plan_scorer_command


def compiled_engines_available() -> bool:
    return (
        java_plan_scorer_command() is not None
        and all(
            os.environ.get(name)
            and Path(os.environ[name]).is_file()
            for name in ("MORPHEUS_NATIVE_SEARCH_EXECUTABLE", "MORPHEUS_CSV_PROFILE_EXECUTABLE")
        )
    )


@pytest.mark.skipif(not compiled_engines_available(), reason="requires real compiled C++ and Java engines")
def test_real_csv_to_cpp_to_java_uses_arbitrary_dataset_and_constraints(monkeypatch):
    monkeypatch.setenv("MORPHEUS_PLAN_SCORER", "java")
    monkeypatch.setenv("MORPHEUS_SEARCH_BACKEND", "native")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    source = (
        "Instrument Code,Charge Amount,Warehouse Zone\n"
        "X-1,420,A\nX-2,1030,B\nX-3,570,A\nX-4,250,C\n"
    )
    operations = [
        {"kind": "point_lookup", "field": "Instrument_Code", "weight": 2},
        {"kind": "filter", "field": "Warehouse_Zone", "weight": 1, "selectivity": 0.5},
    ]
    request = {
        "csv_text": source,
        "queries": operations,
        "constraints": {"memory_mb": 2.0, "update_rate": 10},
        "objective": {"latency": 1.0, "memory": 0.1, "update": 0.5, "build": 0.05},
        "strategy": "exhaustive",
    }
    result = client.post("/api/v2/data/profile-csv", json=request)
    assert result.status_code == 200, result.text
    payload = result.json()
    profile = payload["profile"]
    assert profile["record_count"] == 4
    assert [f["source_name"] for f in profile["fields"]] == [
        "Instrument Code", "Charge Amount", "Warehouse Zone"
    ]
    assert profile["fields"][2]["cardinality"] == 3
    synthesis = payload["synthesis"]
    assert synthesis["winner"] is not None
    assert synthesis["search_summary"]["evaluated_configurations"] > 1
    assert any("compiled Java" in message for message in synthesis["warnings"])
    assert any("compiled C++20" in message for message in synthesis["warnings"])
    assert len(payload["options_by_query"]) == 2
    assert all(any(choice["eligible"] for choice in route["choices"])
               for route in payload["options_by_query"])

    # A truly different uploaded schema must be profiled independently.
    other = client.post("/api/v2/data/profile-csv", json={
        "csv_text": "Region,Available\nEast,yes\nWest,no\nEast,yes\n",
        "queries": [{"kind": "filter", "field": "Region", "weight": 1, "selectivity": 2 / 3}],
        "constraints": {"memory_mb": 1},
    })
    assert other.status_code == 200, other.text
    assert other.json()["profile"]["record_count"] == 3
    assert other.json()["profile"]["source_sha256"] != profile["source_sha256"]
    assert other.json()["profile"]["fields"][0]["source_name"] == "Region"
    assert other.json()["synthesis"]["winner"] is not None

    # Restrict physical-index memory until no evaluated candidate is feasible;
    # neither Java nor C++ may manufacture a winner.
    request["constraints"] = {"memory_mb": 0.00000001, "update_rate": 10}
    refused = client.post("/api/v2/data/profile-csv", json=request)
    assert refused.status_code == 200, refused.text
    assert refused.json()["synthesis"]["winner"] is None
    assert all(not candidate["feasible"] for candidate in refused.json()["synthesis"]["candidates"])
