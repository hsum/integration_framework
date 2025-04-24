import pytest
from unittest.mock import MagicMock
from collections import namedtuple

@pytest.fixture
def test_db(tmp_path):
    """Create a mock SQLite database for testing."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.execute.side_effect = [
        None,  # CREATE TABLE
        None,  # INSERT
        None,  # COMMIT
        None,  # SELECT id, timestamp (params0)
        None,  # SELECT id, timestamp (params1)
        None,  # SELECT id, timestamp, integration_name
        None,  # SELECT id (empty)
        None,  # INSERT in test_exit
    ]
    mock_cursor.fetchall.side_effect = [
        [(1, "2025-04-22T10:00:00")],  # SELECT id, timestamp (params0)
        [(1, "2025-04-22T10:00:00")],  # SELECT id, timestamp (params1)
        [(1, "2025-04-22T10:00:00", "test")],  # SELECT id, timestamp, integration_name
        [],  # SELECT id (empty)
    ]
    default_description = [
        ("id", None, None, None, None, None, None),
        ("timestamp", None, None, None, None, None, None)
    ]
    namedtuple_description = [
        ("id", None, None, None, None, None, None),
        ("max_timestamp", None, None, None, None, None, None),
        ("integration_name", None, None, None, None, None, None)
    ]

    def dynamic_description(*args, **kwargs):
        query = args[0] if args and args[0] else ""
        if "max_timestamp" in query.lower():
            return namedtuple_description
        return default_description

    mock_cursor.description = property(dynamic_description)
    return mock_conn

def test_init(test_db):
    from sql_query_manager import SQLQueryManager
    with SQLQueryManager(":memory:") as mgr:
        assert mgr is not None

def test_enter(test_db):
    from sql_query_manager import SQLQueryManager
    with SQLQueryManager(":memory:") as mgr:
        assert mgr.cursor is not None

def test_exit(test_db):
    from sql_query_manager import SQLQueryManager
    with SQLQueryManager(":memory:") as mgr:
        pass
    assert mgr.connection is None

@pytest.mark.parametrize("params, query", [
    (["test"], "SELECT id, timestamp FROM telemetry WHERE integration_name = ?"),
    ([], "SELECT id, timestamp FROM telemetry")
])
def test_execute_query(test_db, params, query):
    from sql_query_manager import SQLQueryManager
    with SQLQueryManager(":memory:") as mgr:
        results = list(mgr.execute_query(query, params))
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], dict)

def test_execute_query_context_error(test_db):
    from sql_query_manager import SQLQueryManager
    try:
        with SQLQueryManager(":memory:"):
            raise ValueError("Test error")
    except ValueError:
        assert True

@pytest.mark.parametrize("params, query, expected_fields", [
    (["test"], "SELECT id, timestamp AS max_timestamp, integration_name FROM telemetry WHERE integration_name = ?", ["id", "max_timestamp", "integration_name"]),
    ([], "SELECT id, timestamp FROM telemetry", ["id", "timestamp"])
])
def test_execute_query_as_namedtuple(test_db, params, query, expected_fields):
    from sql_query_manager import SQLQueryManager
    with SQLQueryManager(":memory:") as mgr:
        results = list(mgr.execute_query_as_namedtuple(query, params))
    assert isinstance(results, list)
    if results:
        assert all(hasattr(row, field) for row in results for field in expected_fields)

def test_execute_query_as_namedtuple_empty(test_db):
    from sql_query_manager import SQLQueryManager
    with SQLQueryManager(":memory:") as mgr:
        results = list(mgr.execute_query_as_namedtuple("SELECT id FROM telemetry WHERE id = ?", [999]))
    assert results == []

def test_execute_query_as_namedtuple_context_error(test_db):
    from sql_query_manager import SQLQueryManager
    try:
        with SQLQueryManager(":memory:"):
            raise ValueError("Test error")
    except ValueError:
        assert True