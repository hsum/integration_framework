import sqlite3
from datetime import datetime
from pathlib import Path
import csv
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class TelemetryManager:
    """Manages telemetry data logging to a SQLite database."""
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Initialize the telemetry database and table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    integration_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    error TEXT
                )
            """)
            conn.commit()

    def log_run(self, integration_name: str, status: str, duration: float, error: str | None = None) -> None:
        """Log an integration run to the database."""
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO telemetry (integration_name, status, duration, timestamp, error) VALUES (?, ?, ?, ?, ?)",
                (integration_name, status, duration, timestamp, error)
            )
            conn.commit()

    def generate_report(self, period: str) -> None:
        """Generate a telemetry report for a given period (YYYY-MM)."""
        try:
            start_date = datetime.strptime(period, "%Y-%m")
            end_date = (start_date.replace(day=1, month=start_date.month % 12 + 1) if start_date.month < 12
                        else start_date.replace(day=1, month=1, year=start_date.year + 1))
        except ValueError:
            logger.error("Invalid period format. Use YYYY-MM")
            return

        query = """
            SELECT
                integration_name,
                COUNT(*) as run_count,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as error_count,
                AVG(duration) as avg_duration
            FROM telemetry
            WHERE timestamp >= ? AND timestamp < ?
            GROUP BY integration_name
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (start_date.isoformat(), end_date.isoformat()))
            results = cursor.fetchall()

        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"telemetry_report_{period}.csv"
        
        with output_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["integration_name", "run_count", "success_count", "error_count", "avg_duration"])
            for row in results:
                writer.writerow([
                    row[0],  # integration_name
                    row[1],  # run_count
                    row[2],  # success_count
                    row[3],  # error_count
                    row[4]   # avg_duration
                ])
        
        logger.info(f"Generated report: {output_file}")
