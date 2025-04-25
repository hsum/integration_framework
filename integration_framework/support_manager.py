import logging
import backoff
import time

logger = logging.getLogger(__name__)
logger.propagate = True

class SupportManager:
    def __init__(self):
        self.backoff_state = {}
        self.initial_delay = 1.0
        self.multiplier = 2.0
        self.max_delay = 60.0

    def _should_log(self, key: str, current_time: float) -> bool:
        """Return True if enough time has passed since the last log."""
        last_time, retry_count = self.backoff_state.get(key, (0.0, 0))
        delay = min(self.initial_delay * (self.multiplier ** retry_count), self.max_delay)
        logger.debug(f"Key: {key}, Current time: {current_time}, Last time: {last_time}, Retry count: {retry_count}, Delay: {delay}")
        if current_time < last_time + delay:
            self.backoff_state[key] = (last_time, 0)
            return False
        return True

    def log(self, message: str, level: str = "info") -> bool:
        """Log a message without backoff."""
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(message)
        return True

    def notify(self, message: str, integration_name: str = None) -> bool:
        """Notify about an integration event with backoff."""
        key = f"notify_{integration_name or 'default'}"
        result, _ = self.log_with_backoff(key, message)
        return result

    def report_issue(self, issue_type: str, message: str, integration_name: str) -> bool:
        """Report an issue for an integration with backoff.

        Args:
            issue_type (str): Type of issue (e.g., 'bug', 'feature').
            message (str): Description of the issue.
            integration_name (str): Name of the related integration.

        Returns:
            bool: True if the issue was logged, False if backoff prevented logging.
        """
        key = f"issue_{integration_name}"
        result, _ = self.log_with_backoff(key, f"Issue in {integration_name}: {issue_type.capitalize()}: {message}", level="error")
        return result
    
    @backoff.on_predicate(
        backoff.expo,
        predicate=lambda result: not result[0],
        max_tries=3,
        max_time=60.0,
        factor=1.0,
        logger=None,
        on_success=lambda details: details["args"][0].backoff_state.update({details["args"][1]: (details["value"][1], 0)}),
        on_backoff=lambda details: logger.debug(f"Backoff retry: {details}")
    )
    def log_with_backoff(self, key: str, message: str, level: str = "info") -> tuple[bool, float]:
        """Log a message with exponential backoff to reduce frequency over time."""
        current_time = time.time()
        logger.debug(f"Attempting log: Key: {key}, Message: {message}, Level: {level}")
        if self._should_log(key, current_time):
            log_func = getattr(logger, level.lower(), logger.info)
            log_func(message)
            return (True, current_time)
        return (False, current_time)