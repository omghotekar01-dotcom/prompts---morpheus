"""Check that every new frontend example works with the real MORPHEUS engine.

This test loads the same MWS texts shipped to the web application. It does not
substitute a JavaScript estimate or use a mocked synthesis endpoint.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.artifact_codegen import generate_verified_header
from app.engine import synthesize
from app.parser import parse_workload_text


EXAMPLES_FILE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "workloadExamples.ts"


def _examples() -> list[tuple[str, str]]:
    content = EXAMPLES_FILE.read_text(encoding="utf-8")
    samples = re.findall(r'id:\s*"([^"]+)"[\s\S]*?spec:\s*`([^`]*)`', content)
    assert len(samples) == 12, f"Expected 12 synthetic examples, got {len(samples)}"
    assert len({name for name, _ in samples}) == len(samples)
    return samples


@pytest.mark.parametrize(("name", "spec_text"), _examples(), ids=lambda value: value[:30])
def test_example_synthesizes_and_produces_real_cpp20(name: str, spec_text: str) -> None:
    spec = parse_workload_text(spec_text)
    result = synthesize(spec)
    assert result.winner is not None, f"{name}: no feasible design under example constraints"
    artifact = generate_verified_header(spec, result.winner)
    assert artifact.header_source, f"{name}: no generated C++20"
    assert "pragma once" in artifact.header_source or "#include" in artifact.header_source
