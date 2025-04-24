from integration_framework.integrations import Integration
import httpx
import backoff

class WeatherNewsIntegration(Integration):
    """Integration for fetching weather news data."""
    def __init__(self, config, support, name="weather_news"):
        """Initialize the weather news integration."""
        super().__init__(config, support, name)
        self.client = httpx.AsyncClient(
            timeout=config.get("timeout", 10)
        )
        self.api_key = config.get("api_key")
        self.api_url = config.get("api_url", "https://api.weatherapi.com/v1")

    @backoff.on_predicate(
        backoff.expo,
        predicate=lambda result: result.status_code == 429,
        max_tries=3,
        max_time=10.0,
        factor=1.5,
        jitter=backoff.full_jitter
    )
    async def _request(self):
        """Make an HTTP request with backoff for 429 responses."""
        return await self.client.get(
            f"{self.api_url}/current.json",
            params={"key": self.api_key, "q": "auto:ip"}
        )

    async def fetch_data(self):
        """Fetch current weather data from the weather API."""
        response = await self._request()
        return response.json() if response.status_code == 200 else {}

    def postprocess_data(self, data):
        """Extract relevant weather information."""
        return {
            "city": data.get("name"),
            "temperature": data.get("main", {}).get("temp")
        }

    def deliver_results(self, data):
        """Notify about weather updates."""
        self.support.notify(f"Weather for {data.get('city')}: {data.get('temperature')}°C")
