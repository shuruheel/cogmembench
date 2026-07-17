from __future__ import annotations

import hashlib
import json

import pytest

from cogmembench import protocol


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_protocol_lock_reports_missing_external_file_without_masking_drift(
    tmp_path, monkeypatch
) -> None:
    config = tmp_path / "configs" / "protocols"
    config.mkdir(parents=True)
    local = tmp_path / "local.txt"
    local.write_bytes(b"local")
    lock = {
        "protocol_id": "standalone",
        "files": {"local.txt": _sha256(b"local")},
        "external_files": {"external/sibling.txt": _sha256(b"expected")},
    }
    (config / "standalone.json").write_text(json.dumps(lock))
    monkeypatch.setattr(protocol, "ROOT", tmp_path)

    result = protocol.verify_protocol_lock("standalone")

    assert result["locked_files"] == 2
    assert result["verified_files"] == 1
    assert result["unavailable_external_files"] == ["external/sibling.txt"]
    assert result["complete"] is False

    external = tmp_path / "external" / "sibling.txt"
    external.parent.mkdir()
    external.write_bytes(b"drifted")
    with pytest.raises(RuntimeError, match="protocol lock standalone drifted"):
        protocol.verify_protocol_lock("standalone")
