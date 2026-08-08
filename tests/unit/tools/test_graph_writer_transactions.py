"""Unit tests for managed transaction operations."""

import sys
from unittest.mock import MagicMock
from pathlib import Path

# Provide a standalone runnable if needed
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))

from codegraphcontext.tools.indexing.persistence.utils import (
    execute_write_operation,
    execute_read_operation,
    get_backend_type,
)

PASSED = 0
FAILED = 0

def run_test(name, func):
    global PASSED, FAILED
    try:
        func()
        PASSED += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        FAILED += 1
        print(f"  [FAIL] {name}")
        print(f"         {e}")


# ===========================================================================
# Mock Factories
# ===========================================================================
def _make_driver_with_execute_methods():
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session
    return mock_driver, mock_session


def _make_legacy_driver():
    mock_session = MagicMock()
    del mock_session.execute_write
    del mock_session.execute_read
    mock_session.write_transaction = MagicMock()
    mock_session.read_transaction = MagicMock()
    
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session
    return mock_driver, mock_session


def _make_raw_driver():
    mock_session = MagicMock()
    del mock_session.execute_write
    del mock_session.execute_read
    del mock_session.write_transaction
    del mock_session.read_transaction
    
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session
    return mock_driver, mock_session


# ===========================================================================
# Tests
# ===========================================================================

def test_execute_write_neo4j_modern():
    driver, session = _make_driver_with_execute_methods()
    work_fn = MagicMock(return_value="result")
    
    res = execute_write_operation(driver, "neo4j", work_fn)
    
    session.execute_write.assert_called_once_with(work_fn)
    # verify work_fn is NOT called directly, but passed to execute_write
    work_fn.assert_not_called()

def test_execute_write_neo4j_legacy():
    driver, session = _make_legacy_driver()
    work_fn = MagicMock(return_value="result")
    
    res = execute_write_operation(driver, "neo4j", work_fn)
    
    session.write_transaction.assert_called_once_with(work_fn)
    work_fn.assert_not_called()

def test_execute_write_neo4j_fallback():
    driver, session = _make_raw_driver()
    work_fn = MagicMock(return_value="result")
    
    res = execute_write_operation(driver, "neo4j", work_fn)
    
    work_fn.assert_called_once_with(session)
    assert res == "result"

def test_execute_write_other_backend():
    driver, session = _make_driver_with_execute_methods()
    work_fn = MagicMock(return_value="result")
    
    res = execute_write_operation(driver, "kuzudb", work_fn)
    
    # execute_write should NOT be called for kuzudb even if present
    session.execute_write.assert_not_called()
    work_fn.assert_called_once_with(session)
    assert res == "result"

def test_execute_read_neo4j_modern():
    driver, session = _make_driver_with_execute_methods()
    work_fn = MagicMock(return_value="result")
    
    res = execute_read_operation(driver, "neo4j", work_fn)
    
    session.execute_read.assert_called_once_with(work_fn)

def test_get_backend_type():
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = "custom"
    
    driver = MagicMock()
    driver.get_backend_type.return_value = "driver_backend"
    
    # prefers db_manager
    assert get_backend_type(driver, db_manager) == "custom"
    
    # falls back to driver
    db_manager = MagicMock(spec=[])
    assert get_backend_type(driver, db_manager) == "driver_backend"
    
    # falls back to neo4j
    driver = MagicMock(spec=[])
    assert get_backend_type(driver, None) == "neo4j"


if __name__ == "__main__":
    run_test("test_execute_write_neo4j_modern", test_execute_write_neo4j_modern)
    run_test("test_execute_write_neo4j_legacy", test_execute_write_neo4j_legacy)
    run_test("test_execute_write_neo4j_fallback", test_execute_write_neo4j_fallback)
    run_test("test_execute_write_other_backend", test_execute_write_other_backend)
    run_test("test_execute_read_neo4j_modern", test_execute_read_neo4j_modern)
    run_test("test_get_backend_type", test_get_backend_type)
    
    print(f"\nRESULTS: {PASSED} passed, {FAILED} failed")
    if FAILED > 0:
        sys.exit(1)
