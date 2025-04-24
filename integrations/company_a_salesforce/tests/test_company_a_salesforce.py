import pytest
from unittest.mock import patch, MagicMock
from integration_framework.support_manager import SupportManager
from integration_framework.integrations.company_a_salesforce import CompanyASalesforceIntegration
from integration_framework.utils import check_docstrings

def test_init():
    """Test CompanyASalesforceIntegration.__init__."""
    check_docstrings()
    config = {"instance_url": "mock_url", "access_token": "mock_token"}
    support = SupportManager()
    integration = CompanyASalesforceIntegration(config, support, "company_a_salesforce")
    assert integration.name == "company_a_salesforce"
    assert integration.support == support
    assert integration.config == config

def test_fetch_data():
    """Test CompanyASalesforceIntegration.fetch_data."""
    check_docstrings()
    config = {"instance_url": "mock_url", "access_token": "mock_token"}
    support = SupportManager()
    integration = CompanyASalesforceIntegration(config, support, "company_a_salesforce")
    with patch.object(integration.client, "query") as mock_query:
        mock_query.return_value = [{"Id": "001", "Name": "Test Account"}]
        data = integration.fetch_data()
        assert data == [{"Id": "001", "Name": "Test Account"}]
        mock_query.assert_called_with("SELECT Id, Name FROM Account")

def test_postprocess_data():
    """Test CompanyASalesforceIntegration.postprocess_data."""
    check_docstrings()
    config = {"instance_url": "mock_url", "access_token": "mock_token"}
    support = SupportManager()
    integration = CompanyASalesforceIntegration(config, support, "company_a_salesforce")
    data = [{"Id": "001", "Name": "Test Account"}]
    processed = integration.postprocess_data(data)
    assert processed == [{"id": "001", "name": "Test Account"}]

def test_deliver_results():
    """Test CompanyASalesforceIntegration.deliver_results."""
    check_docstrings()
    config = {"instance_url": "mock_url", "access_token": "mock_token"}
    support = SupportManager()
    integration = CompanyASalesforceIntegration(config, support, "company_a_salesforce")
    data = [{"id": "001", "name": "Test Account"}]
    with patch.object(support, "notify") as mock_notify:
        integration.deliver_results(data)
        mock_notify.assert_called_with("Processed 1 records for company_a_salesforce")
