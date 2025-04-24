import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from integration_framework.support_manager import SupportManager
from integration_framework.integrations.weather_news import WeatherNewsIntegration
from integration_framework.utils import check_docstrings

@pytest.mark.asyncio
async def test_init():
    """Test WeatherNewsIntegration.__init__."""
    check_docstrings()
    config = {"api_url": "http://api.example.com/weather"}
    support = SupportManager()
    integration = WeatherNewsIntegration(config, support, "weather_news")
    assert integration.name == "weather_news"
    assert integration.support == support
    assert integration.api_url == "http://api.example.com/weather"

@pytest.mark.asyncio
async def test_fetch_data():
    """Test WeatherNewsIntegration.fetch_data."""
    check_docstrings()
    config = {"api_url": "http://api.example.com/weather"}
    support = SupportManager()
    integration = WeatherNewsIntegration(config, support, "weather_news")
    with patch.object(integration.client, "get", new=AsyncMock()) as mock_get:
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"main": {"temp": 20}, "name": "London"}
        mock_get.return_value = mock_response
        data = await integration.fetch_data()
        assert data == {"main": {"temp": 20}, "name": "London"}

@pytest.mark.asyncio
async def test_postprocess_data():
    """Test WeatherNewsIntegration.postprocess_data."""
    check_docstrings()
    config = {"api_url": "http://api.example.com/weather"}
    support = SupportManager()
    integration = WeatherNewsIntegration(config, support, "weather_news")
    data = {"main": {"temp": 20}, "name": "London"}
    processed = integration.postprocess_data(data)
    assert processed == {"city": "London", "temperature": 20}

@pytest.mark.asyncio
async def test_deliver_results():
    """Test WeatherNewsIntegration.deliver_results."""
    check_docstrings()
    config = {"api_url": "http://api.example.com/weather"}
    support = SupportManager()
    integration = WeatherNewsIntegration(config, support, "weather_news")
    data = {"temperature": 20, "city": "London"}
    with patch.object(support, "notify") as mock_notify:
        integration.deliver_results(data)
        mock_notify.assert_called_with("Weather for London: 20°C")
