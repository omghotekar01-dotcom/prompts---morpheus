from __future__ import annotations

import json
from pathlib import Path

from benchmark.publication_catalog_release_bundle import build_release_bundle
from benchmark.publication_catalog_release_index import build_release_index
from benchmark.verify_publication_release_index_evidence import main


def _hash(ch: str) -> str:
    return ch * 64


def _bundle(revision: str, catalog_ch: str, claims: int) -> dict[str, object]:
    return build_release_bundle(
        source_revision=revision,
        catalog_digest=_hash(catalog_ch),
        verifier_digest=_hash("f"),
        manifest_digests=[_hash("1"), _hash("2")],
        claim_count=claims,
    ).to_dict()


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_cli_verifies_exact_release_evidence(tmp_path: Path, capsys) -> None:
    revision = "a" * 40
    bundles = [_bundle(revision, "3", 2), _bundle(revision, "4", 5)]
    index = build_release_index(bundles).to_dict()

    index_path = tmp_path / "index.json"
    bundle_paths = [tmp_path / "bundle-1.json", tmp_path / "bundle-2.json"]
    _write(index_path, index)
    for path, payload in zip(bundle_paths, bundles, strict=True):
        _write(path, payload)

    assert main([str(index_path), *(str(path) for path in reversed(bundle_paths))]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["verified"] is True
    assert output["release_count"] == 2
    assert output["total_claim_count"] == 7
    assert output["production_deployment_authorized"] is False


def test_cli_rejects_substituted_release_evidence(tmp_path: Path, capsys) -> None:
    revision = "b" * 40
    indexed = [_bundle(revision, "3", 2), _bundle(revision, "4", 2)]
    replacement = _bundle(revision, "5", 2)
    index_path = tmp_path / "index.json"
    first_path = tmp_path / "bundle-1.json"
    replacement_path = tmp_path / "replacement.json"
    _write(index_path, build_release_index(indexed).to_dict())
    _write(first_path, indexed[0])
    _write(replacement_path, replacement)

    assert main([str(index_path), str(first_path), str(replacement_path)]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["verified"] is False
    assert output["production_deployment_authorized"] is False
