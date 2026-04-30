import hashlib

import pytest

from codegraphcontext.core.bundle_registry import BundleRegistry


class _FakeResponse:
    def __init__(self, chunks):
        self._chunks = chunks

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=8192):
        return iter(self._chunks)


def test_download_file_rejects_oversized_bundle(monkeypatch, temp_test_dir):
    output_path = temp_test_dir / "bundle.cgc"

    def _fake_get(*args, **kwargs):
        return _FakeResponse([b"a" * 10, b"b" * 10])

    monkeypatch.setattr("codegraphcontext.core.bundle_registry.requests.get", _fake_get)

    with pytest.raises(ValueError, match="exceeds max allowed size"):
        BundleRegistry.download_file(
            "https://example.com/bundle.cgc",
            output_path,
            max_bytes=15,
        )

    assert not output_path.exists()


def test_download_file_rejects_checksum_mismatch(monkeypatch, temp_test_dir):
    output_path = temp_test_dir / "bundle.cgc"
    expected = hashlib.sha256(b"good").hexdigest()

    def _fake_get(*args, **kwargs):
        return _FakeResponse([b"evil"])

    monkeypatch.setattr("codegraphcontext.core.bundle_registry.requests.get", _fake_get)

    with pytest.raises(ValueError, match="checksum mismatch"):
        BundleRegistry.download_file(
            "https://example.com/bundle.cgc",
            output_path,
            expected_sha256=expected,
        )

    assert not output_path.exists()
