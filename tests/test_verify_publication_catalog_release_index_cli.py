from __future__ import annotations

import json
from pathlib import Path

from benchmark.publication_catalog_release_index import SCHEMA
from benchmark.verify_publication_catalog_release_index_cli import main


def _index() -> dict[str, object]:
    from hashlib import sha256
    import json as _json
    payload = {
        "schema": SCHEMA,
        "source_revision": "a" * 40,
        "release_digests": ["1" * 64, "2" * 64],
        "total_claim_count": 2,
        "production_deployment_authorized": False,
    }
    payload["index_digest"] = sha256(_json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    return payload


def test_cli_accepts_valid_index(tmp_path: Path, capsys) -> None:
    path = tmp_path / "index.json"
    path.write_text(json.dumps(_index()), encoding="utf-8")
    assert main([str(path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["production_deployment_authorized"] is False


def test_cli_rejects_tampered_index(tmp_path: Path, capsys) -> None:
    raw = _index()
    raw["total_claim_count"] = 3
    path = tmp_path / "index.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert main([str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
