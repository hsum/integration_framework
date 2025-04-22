import pytest
from integration_framework.sql_executor import SQLQueryManager
from collections import namedtuple
import sqlite3

@pytest.fixture
def test_db(tmp_path):
    """Create a temporary SQLite database for testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE telemetry (id INTEGER, timestamp TEXT, integration_name TEXT)")
    conn.execute("INSERT INTO telemetry VALUES (1, '2025-04-22T10:00:00', 'test')")
    conn.commit()
    conn.close()
    return db_path

def check_docstrings():
    """Helper to verify docstrings for SQLQueryManager and its methods."""
    assert SQLQueryManager.__doc__ is not None, "SQLQueryManager class missing docstring"
    methods = [
        SQLQueryManager.__init__,
        SQLQueryManager.__enter__,
        SQLQueryManager.__exit__,
        SQLQueryManager.execute_query,
        SQLQueryManager.execute_query_as_namedtuple
    ]
    for method in methods:
        assert method.__doc__ is not None, f"Method {method.__name__} missing docstring"

def test_init(test_db):
    """Test SQLQueryManager.__init__."""
    check_docstrings()
    sql = SQLQueryManager(test_db)
    assert sql.db_path == test_db
    assert sql.connection is None
    assert sql.cursor is None

def test_enter(test_db):
    """Test SQLQueryManager.__enter__."""
    check_docstrings()
    with SQLQueryManager(test_db) as sql:
        assert sql.connection is not None
        assert sql.cursor is not None
        assert isinstance(sql.connection, sqlite3.Connection)
        assert isinstance(sql.cursor, sqlite3.Cursor)

def test_exit(test_db):
    """Test SQLQueryManager.__exit__."""
    check_docstrings()
    sql = SQLQueryManager(test_db)
    with sql as s:
        s.connection.execute("INSERT INTO telemetry VALUES (2, '2025-04-22T11:00:00', 'test2')")
    assert sql.connection is None
    assert sql.cursor is None
    # Verify commit
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM telemetry")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 2

def test_execute_query(test_db):
    """Test SQLQueryManager.execute_query with parameters."""
    check_docstrings()
    with SQLQueryManager(test_db) as sql:
        results = sql.execute_query(
            "SELECT id, timestamp FROM telemetry WHERE integration_name = ?",
            ["test"]
        )
        record = next(results)
        assert isinstance(record, dict)
        assert record["id"] == 1
        assert record["timestamp"] == "2025-04-22T10:00:00"

def test_execute_query_no_params(test_db):
    """Test execute_query without parameters."""
    check_docstrings()
    with SQLQueryManager(test_db) as sql:
        results = sql.execute_query("SELECT id, timestamp FROM telemetry")
        record = next(results)
        assert isinstance(record, dict)
        assert record["id"] == 1
        assert record["timestamp"] == "2025-04-22T10:00:00"

def test_execute_query_context_error():
    """Test execute_query outside context manager."""
    check_docstrings()
    sql = SQLQueryManager("test.db")
    with pytest.raises(ValueError, match="SQLQueryManager must be used within a context manager"):
        next(sql.execute_query("SELECT id FROM telemetry"))

def test_execute_query_as_namedtuple(test_db):
    """Test SQLQueryManager.execute_query_as_namedtuple with parameters."""
    check_docstrings()
    with SQLQueryManager(test_db) as sql:
        results = sql.execute_query_as_namedtuple(
            "SELECT id, timestamp AS max_timestamp, integration_name FROM telemetry WHERE integration_name = ?",
            ["test"]
        )
        record = next(results)
        assert isinstance(record, tuple)
        assert record.id == 1
        assert record.max_timestamp == "2025-04-22T10:00:00"
        assert record.integration_name == "test"
        assert record._fields == ("id", "max_timestamp", "integration_name")

def test_execute_query_as_namedtuple_no_params(test_db):
    """Test execute_query_as_namedtuple without parameters."""
    check_docstrings()
    with SQLQueryManager(test_db) as sql:
        results = sql.execute_query_as_namedtuple("SELECT id, timestamp FROM telemetry")
        record = next(results)
        assert isinstance(record, tuple)
        assert record.id == 1
        assert record.timestamp == "2025-04-22T10:00:00"
        assert record._fields == ("id", "timestamp")

def test_execute_query_as_namedtuple_empty(test_db):
    """Test execute_query_as_namedtuple with no results."""
    check_docstrings()
    with SQLQueryManager(test_db) as sql:
        results = sql.execute_query_as_namedtuple(
            "SELECT id FROM telemetry WHERE integration_name = ?",
            ["nonexistent"]
        )
        assert list(results) == []

def test_execute_query_as_namedtuple_context_error():
    """Test execute_query_as_namedtuple outside context manager."""
    check_docstrings()
    sql = SQLQueryManager("test.db")
    with pytest.raises(ValueError, match="SQLQueryManager must be used within a context manager"):
        next(sql.execute_query_as_namedtuple("SELECT id FROM telemetry"))
