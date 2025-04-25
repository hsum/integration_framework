from integration_framework.integrations import Integration
from integration_framework.support_manager import SupportManager

class HelloWorldIntegration(Integration):
    """Simple hello world integration.

    Returns a static message for testing purposes.
    """
    def __init__(self, config: dict, support: SupportManager, name: str):
        """Initialize the integration with configuration and support.

        Args:
            config (dict): Configuration dictionary.
            support (SupportManager): Support manager instance.
            name (str): Integration name.
        """
        super().__init__(config, support, name)

    def fetch_data(self) -> dict:
        """Fetch a static hello world message.

        Returns:
            dict: Dictionary containing the message.
        """
        return {"message": "Hello, World!"}

    def postprocess_data(self, data: dict) -> dict:
        """Process the fetched message.

        Args:
            data (dict): Raw message data.

        Returns:
            dict: Processed message data.
        """
        return data

    def deliver_results(self, data: dict) -> None:
        """Deliver the processed message via support manager.

        Args:
            data (dict): Processed message data.
        """
        self.support.notify(f"Message from {self.name}: {data['message']}")
