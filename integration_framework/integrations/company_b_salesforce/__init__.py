from integration_framework.integrations import Integration
from vendor.salesforce import SalesforceClient

class CompanyBSalesforceIntegration(Integration):
    """Integration for Company B's Salesforce instance."""
    def __init__(self, config, support, name="company_b_salesforce"):
        """Initialize the Company B Salesforce integration."""
        super().__init__(config, support, name)
        self.client = SalesforceClient(
            instance_url=config.get("instance_url"),
            access_token=config.get("access_token")
        )

    def fetch_data(self):
        """Fetch contact data from Salesforce."""
        return self.client.query("SELECT Id, Name FROM Contact")

    def postprocess_data(self, data):
        """Convert Salesforce contact data to a simplified format."""
        return [{"id": record["Id"], "name": record["Name"]} for record in data]

    def deliver_results(self, data):
        """Notify about processed contacts."""
        self.support.notify(f"Processed {len(data)} records for {self.name}")
