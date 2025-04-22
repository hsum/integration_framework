import logging
from datetime import datetime, UTC
from typing import Optional

class SupportManager:
    """Manages issue reporting and notifications for integrations.

    Maintains a list of issues and provides methods to report issues and send notifications.
    """
    def __init__(self) -> None:
        """Initialize the SupportManager with an empty issues list."""
        self.issues: list[dict] = []
        self.logger = logging.getLogger(__name__)

    def report_issue(self, issue_type: str, message: str, integration_name: Optional[str] = None) -> None:
        """Report an issue and optionally send to an external system.

        Args:
            issue_type: Type of issue (e.g., "config", "runtime").
            message: Issue message.
            integration_name: Name of the integration, if applicable.
        """
        issue = {
            "type": issue_type,
            "message": message,
            "integration_name": integration_name,
            "timestamp": datetime.now(UTC).isoformat()
        }
        self.issues.append(issue)
        self.logger.error(f"Issue reported [{issue_type}]: {message} (Integration: {integration_name or 'N/A'})")

    def notify(self, message: str) -> None:
        """Send a notification message.

        Args:
            message: Notification message to send.
        """
        self.logger.info(f"Notification: {message}")
