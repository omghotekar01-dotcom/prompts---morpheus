from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.csv_profile_api import router


def _native_csv_available() -> bool:
    explicit = os.getenv("MORPHEUS_CSV_PROFILE_EXECUTABLE")
    return (Path(explicit).is_file() if explicit else
            shutil.which("morpheus_csv_profile") is not None)


api = FastAPI()
api.include_router(router)
client = TestClient(api)


@pytest.mark.skipif(not _native_csv_available(), reason="native C++ CSV profiler not built")
def test_real_csv_profile_reflects_submitted_rows_not_example_constants() -> None:
    first = client.post("/api/v2/data/profile-csv", json={
        "csv_text": "id,city\n1,Pune\n2,Pune\n3,Mumbai\n",
    })
    assert first.status_code == 200, first.text
    profile = first.json()["profile"]
    assert profile["record_count"] == 3
    assert profile["fields"] == [
        {"name": "id", "source_name": "id", "type": "uint64", "cardinality": 3},
        {"name": "city", "source_name": "city", "type": "string", "cardinality": 2},
    ]
    assert first.json()["synthesis"] is None
    assert profile["provenance"] == "EXACT_SUBMITTED_CSV_CONTENTS_NATIVE_CPP20"
    assert profile["performance_evidence"] == "NOT_BENCHMARKED"

    changed = client.post("/api/v2/data/profile-csv", json={
        "csv_text": "id,city\n20,Delhi\n20,Delhi\n",
    })
    assert changed.status_code == 200, changed.text
    next_profile = changed.json()["profile"]
    assert next_profile["record_count"] == 2
    assert next_profile["fields"][0]["cardinality"] == 1
    assert next_profile["fields"][1]["cardinality"] == 1


@pytest.mark.skipif(not _native_csv_available(), reason="native C++ CSV profiler not built")
def test_real_csv_profile_can_synthesize_explicit_user_query_workload() -> None:
    response = client.post("/api/v2/data/profile-csv", json={
        "csv_text": "id,city\n31,Pune\n32,Mumbai\n33,Pune\n",
        "queries": [
            {"kind": "point_lookup", "field": "id", "weight": 0.7},
            {"kind": "filter", "field": "city", "weight": 0.3, "selectivity": 0.5},
        ],
        "max_candidates": 100,
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["profile"]["record_count"] == 3
    assert result["synthesis"]["winner"] is not None
    assert result["synthesis"]["search_summary"]["evaluated_configurations"] > 0
    assert len(result["synthesis"]["winner"]["assignments"]) == 2


@pytest.mark.skipif(not _native_csv_available(), reason="native C++ CSV profiler not built")
@pytest.mark.parametrize("bad_csv", ["id,city\n1,Pune\n2\n", "id\n"])
def test_invalid_csv_is_rejected_instead_of_fabricating_data(bad_csv) -> None:
    response = client.post("/api/v2/data/profile-csv", json={"csv_text": bad_csv})
    assert response.status_code == 422


@pytest.mark.skipif(not _native_csv_available(), reason="native C++ CSV profiler not built")
def test_query_referencing_missing_csv_field_is_rejected() -> None:
    response = client.post("/api/v2/data/profile-csv", json={
        "csv_text": "id,city\n1,Pune\n",
        "queries": [{"kind": "point_lookup", "field": "missing"}],
    })
    assert response.status_code == 422


@pytest.mark.skipif(not _native_csv_available(), reason="native C++ CSV profiler not built")
def test_duplicate_and_non_identifier_headers_are_preserved_with_safe_aliases() -> None:
    result = client.post("/api/v2/data/profile-csv", json={
        "csv_text": "Total (INR),Total (INR),class\\n2,3,A\\n3,4,B\\n",
    })
    assert result.status_code == 200, result.text
    profile = result.json()["profile"]
    assert [f["source_name"] for f in profile["fields"]] == ["Total (INR)", "Total (INR)", "class"]
    assert [f["name"] for f in profile["fields"]] == ["Total_INR", "Total_INR_2", "field_3"]
    assert profile["record_count"] == 2
