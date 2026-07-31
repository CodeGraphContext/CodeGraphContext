from unittest.mock import patch
from codegraphcontext.utils.debug_log import (
    critical_logger,
    info_logger,
    error_logger,
    warning_logger,
    debug_logger,
)


def test_critical_logger_exists():
    assert callable(critical_logger)


def test_critical_logger_calls_logger_critical():
    with patch("codegraphcontext.utils.debug_log.logger") as mock_logger:
        with patch("codegraphcontext.utils.debug_log._should_log", return_value=True):
            critical_logger("test critical message")
    mock_logger.critical.assert_called_once_with("test critical message")


def test_critical_logger_respects_should_log_false():
    with patch("codegraphcontext.utils.debug_log.logger") as mock_logger:
        with patch("codegraphcontext.utils.debug_log._should_log", return_value=False):
            critical_logger("should not be logged")
    mock_logger.critical.assert_not_called()


def test_critical_logger_checks_correct_level():
    with patch("codegraphcontext.utils.debug_log._should_log", return_value=False) as mock_should_log:
        with patch("codegraphcontext.utils.debug_log.logger"):
            critical_logger("test")
    mock_should_log.assert_called_once_with("CRITICAL")


def test_critical_logger_returns_none_when_suppressed():
    with patch("codegraphcontext.utils.debug_log._should_log", return_value=False):
        result = critical_logger("suppressed")
    assert result is None


def test_all_loggers_consistent_pattern():
    with patch("codegraphcontext.utils.debug_log.logger") as mock_logger:
        with patch("codegraphcontext.utils.debug_log._should_log", return_value=True):
            critical_logger("c")
            info_logger("i")
            error_logger("e")
            warning_logger("w")
    mock_logger.critical.assert_called_once_with("c")
    mock_logger.info.assert_called_once_with("i")
    mock_logger.error.assert_called_once_with("e")
    mock_logger.warning.assert_called_once_with("w")