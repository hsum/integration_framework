"""Integration base class for the integration framework."""

class Integration:
    """Base class for integrations."""
    def __init__(self, config, support, name):
        self.config = config
        self.support = support
        self.name = name

    def fetch_data(self):
        """Fetch data from the integration source."""
        pass

    def postprocess_data(self, data):
        """Process fetched data."""
        pass

    def deliver_results(self, data):
        """Deliver processed data to the destination."""
        pass
