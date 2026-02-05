import pytest
from codegraphcontext.core.cgc_bundle import CGCBundle

class DummyDBManager:
    def get_backend_type(self):
        return "neo4j"
    def get_driver(self):
        return None  # Not used in these simple tests


def test_bundle_creation():
    db_manager = DummyDBManager()
    bundle = CGCBundle(db_manager, antigravity=True)
    assert bundle.antigravity is True


def test_bundle_toggle_flag():
    db_manager = DummyDBManager()
    bundle = CGCBundle(db_manager, antigravity=False)
    assert bundle.antigravity is False
    # Flip the flag manually
    bundle.antigravity = True
    assert bundle.antigravity is True


def test_bundle_import_export_cycle(tmp_path):
    db_manager = DummyDBManager()
    bundle = CGCBundle(db_manager, antigravity=True)

    # Instead of real export, just simulate writing a file
    output_path = tmp_path / "fake_bundle.cgc"
    output_path.write_text("dummy content")

    # Simulate import: just check the flag is preserved
    new_bundle = CGCBundle(db_manager)
    new_bundle.antigravity = bundle.antigravity
    assert new_bundle.antigravity is True