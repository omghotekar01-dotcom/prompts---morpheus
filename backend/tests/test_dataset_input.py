from __future__ import annotations

import base64
import io

import pytest

from app.dataset_input import excel_to_csv, normalize_csv


def test_unfamiliar_csv_columns_get_safe_unique_identifiers() -> None:
    data = 'Item Price (INR),Student Name,class,Item Price (INR)\n14,Om,A,29\n25,Arya,B,29\n'
    result = normalize_csv(data)
    assert result.source_columns == [
        "Item Price (INR)", "Student Name", "class", "Item Price (INR)"
    ]
    assert len(set(result.canonical_columns)) == 4
    assert result.canonical_columns == ["Item_Price_INR", "Student_Name", "field_3", "Item_Price_INR_2"]
    assert result.csv_text.count("\n") == 3
    assert result.source_sha256


def test_real_csv_with_quoted_newlines_and_commas() -> None:
    data = 'Product (name),Memo\n"Desk, old","Line 1\nLine 2"\n'
    result = normalize_csv(data)
    assert result.canonical_columns[0] == "Product_name"
    assert '"Desk, old"' in result.csv_text
    assert "Line 1\nLine 2" in result.csv_text


def test_invalid_dataset_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_csv("A,B\n1,2\n1\n")
    with pytest.raises(ValueError):
        normalize_csv("A\n")


def test_actual_xlsx_contents_are_converted_without_demo_substitution() -> None:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Teacher upload"
    ws.append(["Customer Name", "Total Cost (INR)", "Area"])
    ws.append(["Pune Store", 79.5, "Pune"])
    ws.append(["Nashik Store", 12.0, "Nashik"])
    stream = io.BytesIO()
    wb.save(stream)
    result = excel_to_csv(base64.b64encode(stream.getvalue()).decode())
    assert result.source_kind == "XLSX"
    assert result.worksheet == "Teacher upload"
    assert result.source_columns[0] == "Customer Name"
    assert result.canonical_columns[1] == "Total_Cost_INR"
    assert "Nashik Store" in result.csv_text
