class SalesforceClient:
    def __init__(self, instance_url, access_token):
        self.instance_url = instance_url
        self.access_token = access_token

    def query(self, soql):
        """Mock query method for Salesforce API."""
        return []
