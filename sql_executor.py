import sqlite3
from collections import namedtuple
from collections.abc import Iterator

class SQLQueryManager:
    """Manages SQLite database queries with context manager support.

    Provides methods to execute SELECT queries, yielding results as dictionaries
    or namedtuples. Ensures database connections are properly managed within
    a context manager for safe resource handling.

    Args:
        db_path (str): Path to the SQLite database file.
    """
    def __init__(self, db_path: str):
        """Initialize the SQLQueryManager with a database path.

        Args:
            db_path (str): Path to the SQLite database file.
        """
        self.db_path = db_path
        self.connection = None
        self.cursor = None

    def __enter__(self):
        """Open a database connection and cursor for query execution.

        Returns:
            SQLQueryManager: Self, for use within a context manager.
        """
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the cursor and connection, committing any changes."""
        if self.connection:
            self.connection.commit()
            self.cursor.close()
            self.connection.close()
            self.cursor = None
            self.connection = None

    def execute_query(self, query: str, params: list = None) -> Iterator[dict[str, any]]:
        """Execute a SELECT query and yield results as dictionaries.

        Args:
            query (str): The SQL SELECT query to execute.
            params (list, optional): Parameters for the query to prevent SQL injection.

        Yields:
            Iterator[dict[str, any]]: Each row as a dictionary with column names as keys.

        Raises:
            ValueError: If called outside a context manager.
            sqlite3.Error: If the query execution fails.
        """
        if self.cursor is None:
            raise ValueError("SQLQueryManager must be used within a context manager")
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            for row in self.cursor:
                yield dict(row)
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Query failed: {e}")

    def execute_query_as_namedtuple(self, query: str, params: list = None) -> Iterator[tuple]:
        """Execute a SELECT query and yield results as namedtuples.

        Args:
            query (str): The SQL SELECT query to execute.
            params (list, optional): Parameters for the query to prevent SQL injection.

        Yields:
            Iterator[tuple]: Each row as a namedtuple with sanitized column names.

        Raises:
            ValueError: If called outside a context manager.
            sqlite3.Error: If the query execution fails.
        """
        if self.cursor is None:
            raise ValueError("SQLQueryManager must be used within a context manager")
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            columns = [description[0] for description in self.cursor.description]
            Record = namedtuple('Record', [col.replace(' ', '_').replace('-', '_') for col in columns])
            for row in self.cursor:
                yield Record(*row)
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Query failed: {e}")
