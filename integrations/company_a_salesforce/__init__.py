from integration_framework.integrations import Integration
from integration_framework.support_manager import SupportManager
from vendor.salesforce import SalesforceClient

class CompanyASalesforceIntegration(Integration):
    """Salesforce integration for Company A.

    Fetches and processes Account data from Salesforce.
    """
    def __init__(self, config: dict, support: SupportManager, name: str):
        """Initialize the integration with configuration and support.

        Args:
            config (dict): Configuration dictionary.
            support (SupportManager): Support manager instance.
            name (str): Integration name.
        """
        super().__init__(config, support, name)
        self.client = SalesforceClient(
            instance_url=config.get("instance_url"),
            access_token=config.get("access_token")
        )

    def fetch_data(self) -> list[dict]:
        """Fetch Account data from Salesforce.

        Returns:
            list[dict]: List of Account records.
        """
        return self.client.query("SELECT Id, Name FROM Account")

    def postprocess_data(self, data: list[dict]) -> list[dict]:
        """Process fetched Account data.

        Args:
            data (list[dict]): Raw Account data.

        Returns:
            list[dict]: Processed data with simplified fields.
        """
        return [{"id": record["Id"], "name": record["Name"]} for record in data]

    def deliver_results(self, data: list[dict]) -> None:
        """Deliver processed data via support manager.

        Args:
            data (list[dict]): Processed Account data.
        """
        self.support.notify(f"Processed {len(data)} records for {self.name}")
