from typing import Any, Dict, List

class SalesforceClient:
    """Mock Salesforce client for querying records."""
    def __init__(self, instance_url: str, access_token: str) -> None:
        self.instance_url = instance_url
        self.access_token = access_token

    def query(self, query: str) -> List[Dict[str, Any]]:
        """Mock a Salesforce query.

        Args:
            query: SOQL query string.

        Returns:
            list: Mocked Salesforce records.
        """
        # Mock implementation for testing
        return [
            {"Id": f"mock_id_{i}", "Name": f"Mock Record {i}", "Field": f"Value {i}"}
            for i in range(3)
        ]

