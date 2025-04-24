import pytest
from unittest.mock import patch, MagicMock
import io
import sys
import importlib.machinery

@pytest.fixture(autouse=True)
def mock_asyncio_sleep():
    """Patch asyncio.sleep globally to skip delays in tests."""
    with patch("asyncio.sleep", return_value=None):
        yield

@pytest.fixture(autouse=True)
def mock_file_open(monkeypatch):
    """Patch builtins.open to avoid file I/O and support YAML/JSON operations."""
    file_contents = {}
    def mock_open(file, mode='r', *args, **kwargs):
        if 'w' in mode:
            file_contents[file] = io.StringIO()
            return file_contents[file]
        elif 'r' in mode and file in file_contents:
            file_contents[file].seek(0)
            return file_contents[file]
        else:
            return io.StringIO()
    monkeypatch.setattr("builtins.open", mock_open)
    yield

@pytest.fixture(autouse=True)
def mock_importlib(monkeypatch):
    """Patch importlib to speed up module loading in tests."""
    def mock_find_spec(name, path=None, target=None):
        if name.startswith("test_integration_framework"):
            return MagicMock(spec=importlib.machinery.ModuleSpec)
        return None
    monkeypatch.setattr("importlib.util.find_spec", mock_find_spec)
    yield
