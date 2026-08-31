import json

from benchmark.publication_claim_manifest import build_publication_claim_manifest
from benchmark.verify_publication_claims_cli import main


def _manifest():
    release = {
        "source_revision": "a" * 40,
        "release_sha256": "b" * 64,
        "publication_claims_authorized": True,
        "production_deployment_authorized": False,
    }
    built = build_publication_claim_manifest(
        release,
        claims=["Latency improved on workload A"],
        benchmark_artifacts={"results.json": "c" * 64},
    )
    return {
        "source_revision": built.source_revision,
        "consensus_release_sha256": built.consensus_release_sha256,
        "benchmark_artifacts": [list(x) for x in built.benchmark_artifacts],
        "claims": list(built.claims),
        "publication_claims_authorized": built.publication_claims_authorized,
        "production_deployment_authorized": built.production_deployment_authorized,
        "manifest_sha256": built.manifest_sha256,
    }


def test_cli_accepts_valid_manifest(tmp_path, capsys):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_manifest()), encoding="utf-8")
    assert main([str(path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["schema"] == "morpheus.publication_claim_verification.v1"
    assert len(output["manifest_sha256"]) == 64


def test_cli_rejects_tampered_manifest(tmp_path, capsys):
    manifest = _manifest()
    manifest["claims"][0] = "A stronger claim that was never reproduced"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert main([str(path)]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["ok"] is False
    assert "digest mismatch" in error["error"]


def test_cli_rejects_invalid_json(tmp_path, capsys):
    path = tmp_path / "manifest.json"
    path.write_text("{not-json", encoding="utf-8")
    assert main([str(path)]) == 2
    assert "not valid JSON" in json.loads(capsys.readouterr().err)["error"]


def test_cli_rejects_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "missing.json")]) == 2
    assert "does not exist" in json.loads(capsys.readouterr().err)["error"]
