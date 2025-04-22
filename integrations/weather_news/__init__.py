from integration_framework.integrations import Integration
from integration_framework.support_manager import SupportManager
from vendor.http_client import HttpClient

class WeatherNewsIntegration(Integration):
    """Integration for fetching weather news.

    Retrieves and processes weather data from an API.
    """
    def __init__(self, config: dict, support: SupportManager, name: str):
        """Initialize the integration with configuration and support.

        Args:
            config (dict): Configuration dictionary with API URL.
            support (SupportManager): Support manager instance.
            name (str): Integration name.
        """
        super().__init__(config, support, name)
        self.client = HttpClient()
        self.api_url = config.get("api_url", "/weather")

    async def fetch_data(self) -> dict:
        """Fetch weather data from the API asynchronously.

        Returns:
            dict: Raw weather data.
        """
        response = await self.client.get(self.api_url)
        return response.json()

    def postprocess_data(self, data: dict) -> dict:
        """Process fetched weather data.

        Args:
            data (dict): Raw weather data.

        Returns:
            dict: Processed data with temperature and city.
        """
        return {"temperature": data["main"]["temp"], "city": data["name"]}

    def deliver_results(self, data: dict) -> None:
        """Deliver processed weather data via support manager.

        Args:
            data (dict): Processed weather data.
        """
        self.support.notify(f"Weather for {data['city']}: {data['temperature']}°C")
