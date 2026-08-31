import json

from benchmark.publication_catalog_release_bundle import build_release_bundle
from benchmark.verify_publication_catalog_release_cli import main, verify_file


def h(ch: str) -> str:
    return ch * 64


def test_cli_verifies_valid_bundle(tmp_path, capsys):
    bundle = build_release_bundle(
        source_revision="a" * 40,
        catalog_digest=h("1"),
        verifier_digest=h("2"),
        manifest_digests=[h("3"), h("4")],
        claim_count=2,
    )
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle.to_dict()), encoding="utf-8")

    result = verify_file(path)
    assert result["valid"] is True
    assert result["release_digest"] == bundle.release_digest
    assert result["manifest_count"] == 2
    assert result["production_deployment_authorized"] is False

    assert main([str(path)]) == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["valid"] is True


def test_cli_fails_closed_on_tampering_and_bad_usage(tmp_path, capsys):
    bundle = build_release_bundle(
        source_revision="b" * 40,
        catalog_digest=h("1"), verifier_digest=h("2"),
        manifest_digests=[h("3"), h("4")], claim_count=2,
    ).to_dict()
    bundle["claim_count"] = 3
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    assert main([str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["valid"] is False
    assert main([]) == 2
    assert json.loads(capsys.readouterr().out)["valid"] is False
