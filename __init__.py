from abc import ABC, abstractmethod
from typing import Iterator, Optional
from .support_manager import SupportManager

class Integration(ABC):
    """Abstract base class for integrations."""
    def __init__(self, config: dict, support: SupportManager, name: Optional[str] = None) -> None:
        self.config = config
        self.support = support
        self.name = name or self.__class__.__name__

    @abstractmethod
    def fetch_data(self) -> Iterator[dict]:
        """Fetch data from the source.

        Yields:
            dict: Data item.
        """
        pass

    @abstractmethod
    def postprocess_data(self, data: Iterator[dict]) -> Iterator[dict]:
        """Process fetched data.

        Args:
            data: Iterator of data items.

        Yields:
            dict: Processed data item.
        """
        pass

    @abstractmethod
    def deliver_results(self, data: Iterator[dict]) -> None:
        """Deliver processed data to the destination.

        Args:
            data: Iterator of processed data items.
        """
        pass

