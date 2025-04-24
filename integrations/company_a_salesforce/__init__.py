from integration_framework.integrations import Integration
from vendor.salesforce import SalesforceClient

class CompanyASalesforceIntegration(Integration):
    """Integration for Company A's Salesforce instance."""
    def __init__(self, config, support, name="company_a_salesforce"):
        """Initialize the Company A Salesforce integration."""
        super().__init__(config, support, name)
        self.client = SalesforceClient(
            instance_url=config.get("instance_url"),
            access_token=config.get("access_token")
        )

    def fetch_data(self):
        """Fetch account data from Salesforce."""
        return self.client.query("SELECT Id, Name FROM Account")

    def postprocess_data(self, data):
        """Convert Salesforce account data to a simplified format."""
        return [{"id": record["Id"], "name": record["Name"]} for record in data]

    def deliver_results(self, data):
        """Notify about processed accounts."""
        self.support.notify(f"Processed {len(data)} records for {self.name}")
