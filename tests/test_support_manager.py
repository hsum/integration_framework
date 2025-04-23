import pytest
from unittest.mock import patch
from integration_framework.support_manager import SupportManager

@pytest.fixture
def support_manager():
    return SupportManager()

def test_log_with_backoff(support_manager, caplog):
    """Test log_with_backoff rate-limits logging with exponential delays."""
    caplog.set_level("INFO")
    key = "test_error"
    message = "Test error message"

    # First log should succeed
    with patch("time.time", return_value=1000.0):
        assert support_manager.log_with_backoff(key, message, level="error")[0] is True
        assert "Test error message" in caplog.text

    # Second log within 1s should be skipped
    caplog.clear()
    with patch("time.time", return_value=1000.5):
        assert support_manager.log_with_backoff(key, message, level="error")[0] is False
        assert "Test error message" not in caplog.text

    # Third log after 1s should succeed
    with patch("time.time", return_value=1001.1):
        assert support_manager.log_with_backoff(key, message, level="error")[0] is True

def test_notify_with_backoff(support_manager, caplog):
    """Test notify uses log_with_backoff."""
    caplog.set_level("INFO")
    with patch("time.time", return_value=1000.0):
        support_manager.notify("Test notification", "test_integration")

def test_report_issue_with_backoff(support_manager, caplog):
    """Test report_issue uses log_with_backoff."""
    caplog.set_level("ERROR")
    with patch("time.time", return_value=1000.0):
        support_manager.report_issue("test_integration", "Test error")
