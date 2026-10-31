from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.csv_profile_api import router


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _has_both_native() -> bool:
    return bool(
        os.getenv("MORPHEUS_CSV_PROFILE_EXECUTABLE")
        and Path(os.environ["MORPHEUS_CSV_PROFILE_EXECUTABLE"]).is_file()
        and os.getenv("MORPHEUS_NATIVE_SEARCH_EXECUTABLE")
        and Path(os.environ["MORPHEUS_NATIVE_SEARCH_EXECUTABLE"]).is_file()
    )


def test_catalog_returns_actual_registry_with_source_and_capabilities() -> None:
    res = client.get("/api/v2/data/catalog")
    assert res.status_code == 200
    names = {entry["id"]: entry for entry in res.json()["primitives"]}
    assert "robin_hood_hash" in names
    assert "bitmap" in names
    assert "ordered_tree" in names
    assert "filter" in names["ordered_tree"]["operations"]
    assert "filter" in names["sorted_array"]["operations"]
    assert names["ordered_tree"]["source_path"] == "core/include/morpheus/bplus_tree.hpp"
    assert all(item["evidence"] == "CATALOG_PRIOR_NOT_A_DATASET_BENCHMARK" for item in names.values())


@pytest.mark.skipif(not _has_both_native(), reason="native C++ search/profiler executables not built")
def test_teacher_csv_schema_records_predicate_candidates_and_generated_cpp() -> None:
    csv_text = "Item Name,Price INR,Area\nMouse,450,Pune\nDesk,950,Nashik\nLamp,180,Pune\n"
    profile_response = client.post("/api/v2/data/profile-csv", json={"csv_text": csv_text})
    assert profile_response.status_code == 200, profile_response.text
    inspected = profile_response.json()["profile"]
    assert inspected["record_count"] == 3
    assert [x["source_name"] for x in inspected["fields"]] == ["Item Name", "Price INR", "Area"]
    assert [x["name"] for x in inspected["fields"]] == ["Item_Name", "Price_INR", "Area"]
    assert inspected["fields"][2]["cardinality"] == 2

    page = client.post("/api/v2/data/page-csv", json={"csv_text": csv_text, "offset": 1, "limit": 1})
    assert page.status_code == 200, page.text
    assert page.json()["records"] == [{"record_index": 2, "values": ["Desk", "950", "Nashik"]}]

    probe = client.post("/api/v2/data/probe-csv", json={
        "csv_text": csv_text, "field": "Area", "operation": "filter", "value": "Pune",
    })
    assert probe.status_code == 200, probe.text
    observed = probe.json()
    assert observed["matched_records"] == 2
    assert observed["total_records"] == 3
    assert observed["matched_selectivity"] == pytest.approx(2 / 3)
    assert [r["record_index"] for r in observed["preview_records"]] == [1, 3]
    assert observed["performance_evidence"] == "NOT_A_BENCHMARK"

    optimized = client.post("/api/v2/data/profile-csv", json={
        "csv_text": csv_text,
        "queries": [{"kind": "filter", "field": "Area", "weight": 1.0,
                     "selectivity": observed["matched_selectivity"]}],
        "max_candidates": 40, "strategy": "exhaustive",
        "constraints": {"memory_mb": 1.0, "update_rate": 0},
    })
    assert optimized.status_code == 200, optimized.text
    data = optimized.json()
    option_map = {item["primitive"]: item for item in data["options_by_query"][0]["choices"]}
    assert all(option_map[name]["eligible"] for name in ["bitmap", "ordered_tree", "sorted_array"])
    assert not option_map["robin_hood_hash"]["eligible"]
    assert data["synthesis"]["search_summary"]["theoretical_configurations"] == 3
    assert data["synthesis"]["search_summary"]["evaluated_configurations"] == 3
    assert data["synthesis"]["winner"] is not None
    assert data["generated_artifact"]["source"].startswith("#pragma once")
    assert "Item_Name" in data["generated_artifact"]["source"]
    assert "GENERATED_NOT_COMPILE_OR_BEHAVIOR_VERIFIED" == data["generated_artifact"]["status"]

    constrained = client.post("/api/v2/data/profile-csv", json={
        "csv_text": csv_text,
        "queries": [{"kind": "filter", "field": "Area", "selectivity": 2 / 3}],
        "constraints": {"memory_mb": 0.000001},
    })
    assert constrained.status_code == 200
    assert constrained.json()["synthesis"]["winner"] is None


@pytest.mark.skipif(not _has_both_native(), reason="native C++ search/profiler executables not built")
def test_swapping_dataset_changes_profile_and_allocation() -> None:
    def evaluate(csv: str) -> dict:
        response = client.post("/api/v2/data/profile-csv", json={
            "csv_text": csv,
            "queries": [{"kind": "point_lookup", "field": "ProductID", "weight": 1}],
            "strategy": "exhaustive",
        })
        assert response.status_code == 200, response.text
        return response.json()

    small = evaluate("ProductID,Label\n1,Pen\n2,Ink\n")
    big = evaluate("ProductID,Label\n1,Pen\n2,Ink\n3,Book\n4,Stapler\n5,Glue\n")
    assert small["profile"]["record_count"] == 2
    assert big["profile"]["record_count"] == 5
    assert small["profile"]["source_sha256"] != big["profile"]["source_sha256"]
    assert small["synthesis"]["winner"]["predicted_memory_mb"] < big["synthesis"]["winner"]["predicted_memory_mb"]


def test_invalid_browse_and_probe_reject_unrelated_columns() -> None:
    response = client.post("/api/v2/data/probe-csv", json={
        "csv_text": "Fruit,Stock\nApple,12\n", "field": "RollID",
        "operation": "point_lookup", "value": "1",
    })
    assert response.status_code == 422
