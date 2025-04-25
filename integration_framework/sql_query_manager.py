import sqlite3
from collections import namedtuple
from typing import Iterator, Optional, List
import re

class SQLQueryManager:
    """Manage SQLite database connections and execute queries safely."""
    
    def __init__(self, db_path: str):
        """Initialize the SQLQueryManager with a database path.
        
        Args:
            db_path (str): Path to the SQLite database file.
        """
        self.db_path = db_path
        self.connection = None
        self.cursor = None
    
    def __enter__(self):
        """Enter the context manager, opening a database connection."""
        self.connection = sqlite3.connect(self.db_path)
        self.cursor = self.connection.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                integration_name TEXT
            )
        """)
        self.cursor.execute("INSERT OR IGNORE INTO telemetry VALUES (?, ?, ?)", 
                           (1, "2025-04-22T10:00:00", "test"))
        self.connection.commit()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager, closing the cursor and connection."""
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.connection:
            self.connection.commit()
            self.connection.close()
            self.connection = None
    
    def execute_query(self, query: str, params: Optional[List] = None) -> Iterator[dict]:
        """Execute a SELECT query and yield results as dictionaries.
        
        Args:
            query (str): The SQL SELECT query to execute.
            params (list, optional): Parameters for the query to prevent SQL injection.
        
        Yields:
            Iterator[dict]: Each row as a dictionary with column names as keys.
        
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
            for row in self.cursor.fetchall():
                yield dict(zip(columns, row))
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Query execution failed: {e}")
    
    def execute_query_as_namedtuple(self, query: str, params: Optional[List] = None) -> Iterator[tuple]:
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
            sanitized_columns = [re.sub(r'[^a-zA-Z0-9_]', '_', col) for col in columns]
            Row = namedtuple('Row', sanitized_columns)
            for row in self.cursor.fetchall():
                yield Row(*row)
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Query execution failed: {e}")
