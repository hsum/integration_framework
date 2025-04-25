import pytest
import asyncio
import sys
import logging
import importlib
from pathlib import Path
import yaml
import json
from datetime import datetime, timedelta
from integration_framework.batch import BatchRunner
from integration_framework.support_manager import SupportManager
from integration_framework.sql_query_manager import SQLQueryManager
from integration_framework.telemetry import TelemetryManager
from integration_framework.integrations import Integration
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import inspect

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@pytest.fixture
def runner(tmp_path):
    """Create a BatchRunner with a temporary integrations directory."""
    runner = BatchRunner()
    runner.integrations_dir = tmp_path / "test_integration_framework" / "integrations"
    runner.integrations_dir.mkdir(parents=True)
    (tmp_path / "test_integration_framework" / "__init__.py").touch()
    (runner.integrations_dir / "__init__.py").touch()
    runner._is_test = True
    return runner

def check_docstrings():
    """Verify docstrings for BatchRunner and its public methods."""
    assert BatchRunner.__doc__, "BatchRunner class missing docstring"
    methods = [
        method for method_name, method in inspect.getmembers(BatchRunner, inspect.isfunction)
        if not method_name.startswith('_')
    ]
    for method in methods:
        assert method.__doc__, f"Method {method.__name__} missing docstring"

@pytest.mark.asyncio
async def test_init(runner):
    """Test BatchRunner.__init__."""
    check_docstrings()
    assert isinstance(runner.integrations_dir, Path)
    assert isinstance(runner.support, SupportManager)
    assert isinstance(runner.sql_manager, SQLQueryManager)
    assert isinstance(runner.telemetry, TelemetryManager)
    assert runner.cache_file == Path("validation_cache.json")
    assert runner.cache_ttl == timedelta(hours=24)

def test_load_integration(runner):
    """Test BatchRunner.load_integration."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    (int_dir / "__init__.py").touch()
    class TestIntegration(Integration):
        def __init__(self, config, support, name):
            super().__init__(config, support, name)
        def fetch_data(self): pass
        def postprocess_data(self, data): pass
        def deliver_results(self, data): pass
    mock_module = MagicMock()
    mock_module.TestIntegration = TestIntegration
    mock_spec = MagicMock()
    with patch("importlib.util.find_spec", return_value=mock_spec), \
         patch("importlib.import_module", return_value=mock_module) as mock_import:
        integration_class = runner.load_integration("test_integration")
        assert integration_class.__name__ == "TestIntegration"
        mock_import.assert_called_with("test_integration_framework.integrations.test_integration")

def test_load_config(runner):
    """Test BatchRunner.load_config."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    config_path = int_dir / "config.yaml"
    with config_path.open("w") as f:
        yaml.safe_dump({"enabled": True}, f)
    config = runner.load_config("test_integration")
    assert config == {"enabled": True}
    assert runner.load_config("nonexistent") == {}

def test_load_metadata(runner):
    """Test BatchRunner.load_metadata."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    metadata_path = int_dir / "metadata.yaml"
    with metadata_path.open("w") as f:
        yaml.safe_dump({"version": "1.0.0", "tags": ["test"], "description": "Test integration"}, f)
    metadata = runner.load_metadata("test_integration")
    assert metadata == {"version": "1.0.0", "tags": ["test"], "description": "Test integration"}
    assert runner.load_metadata("nonexistent") == {}

def test_load_validation_cache(runner, tmp_path):
    """Test BatchRunner.load_validation_cache."""
    check_docstrings()
    runner.cache_file = tmp_path / "validation_cache.json"
    with runner.cache_file.open("w") as f:
        json.dump({"integrations": {"test": {"valid": True, "timestamp": "2025-04-22T10:00:00"}}}, f)
    cache = runner.load_validation_cache()
    assert cache == {"integrations": {"test": {"valid": True, "timestamp": "2025-04-22T10:00:00"}}}
    runner.cache_file = tmp_path / "nonexistent.json"
    assert runner.load_validation_cache() == {"integrations": {}}

def test_save_validation_cache(runner, tmp_path):
    """Test BatchRunner.save_validation_cache."""
    check_docstrings()
    runner.cache_file = tmp_path / "validation_cache.json"
    cache = {"integrations": {"test": {"valid": True, "timestamp": "2025-04-22T10:00:00"}}}
    runner.save_validation_cache(cache)
    with runner.cache_file.open("r") as f:
        saved = json.load(f)
    assert saved == cache

def test_get_last_updated(runner, tmp_path):
    """Test BatchRunner.get_last_updated."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "metadata.yaml").open("w") as f:
        yaml.safe_dump({"last_updated": "2025-04-22T10:00:00"}, f)
    with patch("integration_framework.sql_query_manager.SQLQueryManager") as MockSQL:
        mock_instance = MockSQL.return_value.__enter__.return_value
        mock_instance.execute_query.return_value = iter([])
        timestamp = runner.get_last_updated("test_integration")
        assert timestamp == "2025-04-22T10:00:00"

def test_validate_integration(runner, tmp_path):
    """Test BatchRunner.validate_integration."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": True}, f)
    (int_dir / "__init__.py").touch()
    class TestIntegration(Integration):
        def __init__(self, config, support, name):
            super().__init__(config, support, name)
        def fetch_data(self): pass
        def postprocess_data(self, data): pass
        def deliver_results(self, data): pass
    mock_module = MagicMock()
    mock_module.TestIntegration = TestIntegration
    mock_spec = MagicMock()
    with patch("importlib.util.find_spec", return_value=mock_spec), \
         patch("importlib.import_module", return_value=mock_module):
        runner.cache_file = tmp_path / "validation_cache.json"
        assert runner.validate_integration("test_integration") == True

def test_run_integration(runner):
    """Test BatchRunner.run_integration."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": True}, f)
    (int_dir / "__init__.py").touch()
    class TestIntegration(Integration):
        def __init__(self, config, support, name):
            super().__init__(config, support, name)
        def fetch_data(self): return []
        def postprocess_data(self, data): return data
        def deliver_results(self, data): pass
    mock_module = MagicMock()
    mock_module.TestIntegration = TestIntegration
    mock_spec = MagicMock()
    with patch("importlib.util.find_spec", return_value=mock_spec), \
         patch("importlib.import_module", return_value=mock_module), \
         patch.object(runner, "load_config", return_value={"enabled": True}):
        with patch.object(runner.support, "notify") as mock_notify, \
             patch.object(runner.telemetry, "log_run") as mock_telemetry:
            runner.run_integration("test_integration")
            mock_notify.assert_called_once()

def test_get_integrations(runner):
    """Test BatchRunner.get_integrations."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "__init__.py").open("w") as f:
        f.write("")
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": True}, f)
    integrations = runner.get_integrations()
    assert integrations == ["test_integration"]

@pytest.mark.asyncio
async def test_run_filtered(runner):
    """Test BatchRunner.run_filtered."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": True}, f)
    with (int_dir / "metadata.yaml").open("w") as f:
        yaml.safe_dump({"tags": ["test"], "description": "Test integration"}, f)
    (int_dir / "__init__.py").touch()
    class TestIntegration(Integration):
        def __init__(self, config, support, name):
            super().__init__(config, support, name)
        def fetch_data(self): return []
        def postprocess_data(self, data): return data
        def deliver_results(self, data): pass
    mock_module = MagicMock()
    mock_module.TestIntegration = TestIntegration
    mock_spec = MagicMock()
    with patch("importlib.util.find_spec", return_value=mock_spec), \
         patch("importlib.import_module", return_value=mock_module):
        with patch.object(runner.support, "notify") as mock_notify:
            await runner.run_filtered(name="test_integration", parallel="asyncio")
            mock_notify.assert_called_once()

def test_filter_integrations(runner):
    """Test BatchRunner.filter_integrations."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": True}, f)
    with (int_dir / "metadata.yaml").open("w") as f:
        yaml.safe_dump({
            "tags": ["test"],
            "business_contact": "jane.doe@client.com",
            "technical_contact": "john.smith@client.com",
            "description": "Test integration",
            "last_updated": "2025-04-22T10:00:00"
        }, f)
    (int_dir / "__init__.py").touch()
    integrations, hash_value = runner.filter_integrations(
        partial_name="test",
        tags=["test"],
        business_contact="jane.doe@client.com",
        last_updated_after="2025-04-01"
    )
    assert integrations == ["test_integration"]
    assert len(hash_value) == 8

def test_list_integrations(runner, capsys):
    """Test BatchRunner.list_integrations."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": True}, f)
    with (int_dir / "__init__.py").open("w") as f:
        f.write("")
    with (int_dir / "metadata.yaml").open("w") as f:
        yaml.safe_dump({
            "business_contact": "jane.doe@client.com",
            "technical_contact": "john.smith@client.com",
            "tags": ["test"],
            "description": "Test integration",
            "version": "1.0.0",
            "last_updated": "2025-04-22T10:00:00"
        }, f)
    with patch("integration_framework.sql_query_manager.SQLQueryManager") as MockSQL:
        mock_instance = MockSQL.return_value.__enter__.return_value
        mock_instance.execute_query.return_value = iter([{"MAX(timestamp)": "2025-04-22T10:00:00"}])
        runner.list_integrations(partial_name="test")
        captured = capsys.readouterr()
        assert "test_integration" in captured.out
        assert "jane.doe@client.com" in captured.out
        assert "Criteria Hash" in captured.out

def test_report_issue(runner, capsys):
    """Test BatchRunner.report_issue."""
    check_docstrings()
    with patch.object(runner.support, "report_issue") as mock_report:
        runner.report_issue("bug", "Test issue", "test_integration")
        mock_report.assert_called_once_with("bug", "Test issue", "test_integration")
        captured = capsys.readouterr()
        assert "Issue reported: bug - Test issue" in captured.out

def test_generate_telemetry_report(runner, tmp_path):
    """Test BatchRunner.generate_telemetry_report."""
    check_docstrings()
    with patch.object(runner.telemetry, "generate_report") as mock_report:
        runner.generate_telemetry_report("2025-04")
        mock_report.assert_called_once_with("2025-04")
