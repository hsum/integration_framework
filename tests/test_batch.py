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
from integration_framework.sql_executor import SQLQueryManager
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import inspect

# Configure logging for test debugging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@pytest.fixture
def runner(tmp_path):
    """Create a BatchRunner with a temporary integrations directory."""
    runner = BatchRunner()
    # Set integrations_dir to tmp_path/test_integration_framework/integrations
    runner.integrations_dir = tmp_path / "test_integration_framework" / "integrations"
    runner.integrations_dir.mkdir(parents=True)
    # Create test_integration_framework and integrations packages
    (tmp_path / "test_integration_framework" / "__init__.py").touch()
    (runner.integrations_dir / "__init__.py").touch()
    # Set test flag for load_integration
    runner._is_test = True
    return runner

def check_docstrings():
    """Helper to verify docstrings for BatchRunner and its public methods."""
    assert BatchRunner.__doc__ is not None, "BatchRunner class missing docstring"
    methods = [
        method for method_name, method in inspect.getmembers(BatchRunner, inspect.isfunction)
        if not method_name.startswith('_')
    ]
    for method in methods:
        assert method.__doc__ is not None, f"Method {method.__name__} missing docstring"

@pytest.mark.asyncio
async def test_init(runner):
    """Test BatchRunner.__init__."""
    check_docstrings()
    assert isinstance(runner.integrations_dir, Path)
    assert isinstance(runner.support, SupportManager)
    assert isinstance(runner.sql_manager, SQLQueryManager)
    assert runner.cache_file == Path("validation_cache.json")
    assert runner.cache_ttl == timedelta(hours=24)

def test_load_integration(runner):
    """Test BatchRunner.load_integration."""
    check_docstrings()
    # Create a mock integration directory (not used for class definition)
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    (int_dir / "__init__.py").touch()
    # Define MockIntegrationClass
    class MockIntegrationClass:
        pass
    # Mock Integration in both namespaces
    with patch("integration_framework.integrations.Integration", MockIntegrationClass), \
         patch("integration_framework.batch.Integration", MockIntegrationClass):
        # Define TestIntegration class inheriting from MockIntegrationClass
        class TestIntegration(MockIntegrationClass):
            def __init__(self, config, support, name):
                self.config = config
                self.support = support
                self.name = name
            def fetch_data(self): pass
            def postprocess_data(self, data): pass
            def deliver_results(self, data): pass
        # Create a mock module to return TestIntegration
        mock_module = MagicMock()
        mock_module.TestIntegration = TestIntegration
        # Patch importlib.import_module to return mock_module
        with patch("importlib.import_module", return_value=mock_module):
            # Temporarily add tmp_path to sys.path
            original_sys_path = sys.path.copy()
            sys.path.append(str(runner.integrations_dir.parent.parent))  # tmp_path
            try:
                logger.debug(f"sys.path: {sys.path}")
                logger.debug(f"Attempting to load integration 'test_integration' from {runner.integrations_dir}")
                logger.debug(f"Integration class: {MockIntegrationClass}")
                logger.debug(f"TestIntegration MRO: {TestIntegration.__mro__}")
                importlib.invalidate_caches()  # Refresh module cache
                spec = importlib.util.find_spec("test_integration_framework.integrations.test_integration")
                logger.debug(f"Module spec: {spec}")
                integration_class = runner.load_integration("test_integration")
                logger.debug(f"Loaded integration class: {integration_class}")
                logger.debug(f"TestIntegration type: {type(TestIntegration)}")
                logger.debug(f"issubclass(TestIntegration, MockIntegrationClass): {issubclass(TestIntegration, MockIntegrationClass)}")
                assert integration_class is not None, "Integration class is None"
                assert integration_class.__name__ == "TestIntegration"
            finally:
                sys.path = original_sys_path
    assert runner.load_integration("nonexistent") is None

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
        yaml.safe_dump({"version": "1.0.0"}, f)
    metadata = runner.load_metadata("test_integration")
    assert metadata == {"version": "1.0.0"}
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
    # Mock SQLQueryManager to return no results, forcing metadata fallback
    with patch("integration_framework.sql_executor.SQLQueryManager") as MockSQL:
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
        yaml.safe_dump({"enabled": False}, f)
    assert runner.validate_integration("test_integration") == True
    # Test cache
    runner.cache_file = tmp_path / "validation_cache.json"
    cache = {
        "integrations": {
            "test_integration": {
                "valid": True,
                "timestamp": datetime.now().isoformat()
            }
        }
    }
    runner.save_validation_cache(cache)
    assert runner.validate_integration("test_integration") == True

@pytest.mark.asyncio
async def test_run_integration(runner):
    """Test BatchRunner.run_integration."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": False}, f)
    (int_dir / "__init__.py").touch()
    # Define MockIntegrationClass
    class MockIntegrationClass:
        pass
    # Mock Integration in both namespaces
    with patch("integration_framework.integrations.Integration", MockIntegrationClass), \
         patch("integration_framework.batch.Integration", MockIntegrationClass):
        # Define TestIntegration class inheriting from MockIntegrationClass
        class TestIntegration(MockIntegrationClass):
            def __init__(self, config, support, name):
                self.config = config
                self.support = support
                self.name = name
            def fetch_data(self): return []
            def postprocess_data(self, data): return data
            def deliver_results(self, data): pass
        # Create a mock module to return TestIntegration
        mock_module = MagicMock()
        mock_module.TestIntegration = TestIntegration
        # Patch importlib.import_module to return mock_module
        with patch("importlib.import_module", return_value=mock_module):
            # Temporarily add tmp_path to sys.path
            original_sys_path = sys.path.copy()
            sys.path.append(str(runner.integrations_dir.parent.parent))  # tmp_path
            try:
                importlib.invalidate_caches()  # Refresh module cache
                spec = importlib.util.find_spec("test_integration_framework.integrations.test_integration")
                logger.debug(f"Module spec: {spec}")
                logger.debug(f"Integration class: {MockIntegrationClass}")
                logger.debug(f"TestIntegration MRO: {TestIntegration.__mro__}")
                logger.debug(f"TestIntegration type: {type(TestIntegration)}")
                logger.debug(f"issubclass(TestIntegration, MockIntegrationClass): {issubclass(TestIntegration, MockIntegrationClass)}")
                with patch.object(runner.support, "notify") as mock_notify:
                    runner.run_integration("test_integration")
                    mock_notify.assert_not_called()
            finally:
                sys.path = original_sys_path

@pytest.mark.asyncio
async def test_run_integration_async(runner):
    """Test BatchRunner.run_integration_async."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": False}, f)
    await runner.run_integration_async("test_integration")
    # No assertion; just ensure it runs

def test_run_integration_process(runner):
    """Test BatchRunner.run_integration_process."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": False}, f)
    runner.run_integration_process("test_integration")
    # No assertion; just ensure it runs

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
async def test_run_all(runner):
    """Test BatchRunner.run_all."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": False}, f)
    with (int_dir / "__init__.py").open("w") as f:
        f.write("")
    await runner.run_all(verbose=False, parallel="asyncio")
    # No assertion; just ensure it runs

def test_run_single(runner):
    """Test BatchRunner.run_single."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": False}, f)
    with (int_dir / "__init__.py").open("w") as f:
        f.write("")
    with patch.object(runner.support, "report_issue") as mock_report:
        runner.run_single("nonexistent")
        mock_report.assert_called_once()
    runner.run_single("test_integration")

def test_run_by_tag(runner):
    """Test BatchRunner.run_by_tag."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": False}, f)
    with (int_dir / "metadata.yaml").open("w") as f:
        yaml.safe_dump({"tags": ["test"]}, f)
    with (int_dir / "__init__.py").open("w") as f:
        f.write("")
    runner.run_by_tag("test")
    # No assertion; just ensure it runs

def test_validate(runner):
    """Test BatchRunner.validate."""
    check_docstrings()
    int_dir = runner.integrations_dir / "test_integration"
    int_dir.mkdir()
    with (int_dir / "config.yaml").open("w") as f:
        yaml.safe_dump({"enabled": False}, f)
    with (int_dir / "__init__.py").open("w") as f:
        f.write("")
    runner.validate()
    # No assertion; just ensure it runs

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
            "version": "1.0.0"
        }, f)
    with patch("integration_framework.sql_executor.SQLQueryManager") as MockSQL:
        mock_instance = MockSQL.return_value.__enter__.return_value
        mock_instance.execute_query.return_value = iter([{"MAX(timestamp)": "2025-04-22T10:00:00"}])
        runner.list_integrations()
        captured = capsys.readouterr()
        assert "test_integration" in captured.out
        assert "jane.doe@client.com" in captured.out
        assert "Test integration" in captured.out
