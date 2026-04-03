"""
PoC test for CWE-22: Arbitrary file read via viz server /api/file endpoint.

The /api/file endpoint previously accepted a ``path`` query parameter and
read any file from the filesystem without path validation.  This test suite
confirms that:

1. Files within the configured base directory are served normally.
2. Absolute paths outside the base directory are rejected with 403.
3. ``..`` traversal sequences that escape the base directory are blocked.
4. Symlinks pointing outside the base directory are blocked.
5. When no base directory is configured, all reads are rejected.
6. Relative paths (which could resolve anywhere) are rejected.
"""
import os
import pytest

from codegraphcontext.viz.server import app


@pytest.fixture
def base_dir(tmp_path):
    """Create a temporary base directory with sample files."""
    (tmp_path / "allowed.txt").write_text("allowed content")

    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested content")

    return tmp_path


@pytest.fixture
def client(base_dir):
    """Return a TestClient whose /api/file is restricted to *base_dir*."""
    from fastapi.testclient import TestClient
    from codegraphcontext.viz import server as srv

    srv._allowed_base_dir = str(base_dir)
    yield TestClient(app)
    srv._allowed_base_dir = None          # clean up


class TestPathTraversal:
    """Verify the /api/file endpoint blocks path-traversal attacks."""

    def test_read_allowed_file(self, client, base_dir):
        """Reading a file inside the allowed base dir works."""
        resp = client.get("/api/file", params={"path": str(base_dir / "allowed.txt")})
        assert resp.status_code == 200
        assert resp.json()["content"] == "allowed content"

    def test_read_nested_allowed_file(self, client, base_dir):
        """Reading a nested file inside the allowed base dir works."""
        resp = client.get("/api/file", params={"path": str(base_dir / "sub" / "nested.txt")})
        assert resp.status_code == 200
        assert resp.json()["content"] == "nested content"

    def test_absolute_path_outside_base(self, client):
        """Absolute path pointing outside the base dir → 403."""
        resp = client.get("/api/file", params={"path": "/etc/passwd"})
        assert resp.status_code == 403

    def test_traversal_via_dotdot(self, client, base_dir):
        """Path with ``..`` components escaping the base dir → 403."""
        traversal = str(base_dir / "sub" / ".." / ".." / "etc" / "passwd")
        resp = client.get("/api/file", params={"path": traversal})
        assert resp.status_code == 403

    def test_symlink_escape(self, client, base_dir):
        """Symlink inside base_dir targeting an external file → 403."""
        link = base_dir / "escape_link"
        try:
            os.symlink("/etc/passwd", str(link))
        except (OSError, NotImplementedError):
            pytest.skip("Cannot create symlinks on this platform")

        resp = client.get("/api/file", params={"path": str(link)})
        assert resp.status_code == 403

    def test_no_base_dir_configured(self):
        """When no base directory is set, all reads → 403."""
        from fastapi.testclient import TestClient
        from codegraphcontext.viz import server as srv

        old = srv._allowed_base_dir
        try:
            srv._allowed_base_dir = None
            resp = TestClient(app).get("/api/file", params={"path": "/etc/passwd"})
            assert resp.status_code == 403
        finally:
            srv._allowed_base_dir = old

    def test_relative_path(self, client):
        """Relative paths (resolve to unpredictable locations) → 403."""
        resp = client.get("/api/file", params={"path": "../../etc/passwd"})
        assert resp.status_code == 403
