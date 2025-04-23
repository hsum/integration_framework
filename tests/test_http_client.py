import pytest
import time
from unittest.mock import patch, MagicMock
import httpx
from vendor.http_client import HttpClient, HttpResponse

@pytest.fixture
def http_client():
    """Create an HttpClient instance with default parameters."""
    return HttpClient(timeout=5, initial_delay=1.0, multiplier=2.0, max_retries=5)

def test_retry_with_backoff_success(http_client):
    """Test retry_with_backoff succeeds on first attempt."""
    mock_response = MagicMock(status_code=200, content=b"", headers={}, request=None)
    with patch.object(http_client.client, 'request', return_value=mock_response) as mock_request:
        response = http_client.get("http://example.com")
        assert response.status_code == 200
        assert mock_request.call_count == 1

def test_retry_with_backoff_throttling(http_client):
    """Test retry_with_backoff retries on 429 and succeeds."""
    mock_responses = [
        MagicMock(status_code=429, content=b"", headers={}, request=None),
        MagicMock(status_code=429, content=b"", headers={}, request=None),
        MagicMock(status_code=200, content=b"", headers={}, request=None),
    ]
    start_time = time.time()
    with patch.object(http_client.client, 'request', side_effect=mock_responses) as mock_request:
        response = http_client.get("http://example.com")
        assert response.status_code == 200
        assert mock_request.call_count == 3
        assert time.time() - start_time >= 0.1  # Initial factor

def test_retry_with_backoff_max_retries(http_client):
    """Test retry_with_backoff fails after max retries."""
    mock_response = MagicMock(status_code=429, content=b"", headers={}, request=None)
    with patch.object(http_client.client, 'request', return_value=mock_response):
        with pytest.raises(httpx.RequestError):
            http_client.get("http://example.com")

def test_retry_with_backoff_jitter(http_client):
    """Test retry_with_backoff applies jitter."""
    mock_responses = [
        MagicMock(status_code=429, content=b"", headers={}, request=None),
        MagicMock(status_code=200, content=b"", headers={}, request=None),
    ]
    with patch.object(http_client.client, 'request', side_effect=mock_responses),          patch('random.uniform', return_value=0.1):  # Fixed jitter for predictability
        response = http_client.get("http://example.com")
        assert response.status_code == 200

def test_configurable_backoff():
    """Test HttpClient with custom backoff parameters."""
    client = HttpClient(
        timeout=10,
        initial_delay=0.1,
        max_retries=3,
        max_delay=10.0,
        multiplier=1.5,
        jitter_factor=0.2
    )
    mock_responses = [
        MagicMock(status_code=429, content=b"", headers={}, request=None),
        MagicMock(status_code=200, content=b"", headers={}, request=None),
    ]
    with patch.object(client.client, 'request', side_effect=mock_responses),          patch('random.uniform', return_value=0.0):  # No jitter for exact timing
        response = client.get("http://example.com")
        assert response.status_code == 200
