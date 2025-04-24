import httpx
import backoff
from collections import namedtuple

HttpResponse = namedtuple("HttpResponse", ["status_code", "content", "headers"])

class HttpClient:
    def __init__(self, timeout=5, initial_delay=1.0, max_retries=5, max_delay=60.0, 
                 multiplier=2.0, jitter_factor=0.0):
        self.timeout = timeout
        self.factor = initial_delay * multiplier
        self.max_retries = max_retries
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor
        self.client = httpx.Client(timeout=timeout)

    def _get_jitter(self):
        """Return jitter callable based on jitter_factor."""
        return backoff.full_jitter if self.jitter_factor > 0 else lambda x: x

    @backoff.on_predicate(
        backoff.expo,
        predicate=lambda result: result[0],
        max_tries=5,
        max_time=60.0,
        factor=2.0,
        jitter=backoff.full_jitter,
        logger=None
    )
    def request(self, method: str, url: str, headers: dict[str, str] | None = None, 
                data=None) -> tuple[bool, HttpResponse]:
        """Make an HTTP request with exponential backoff for 429 responses."""
        try:
            response = self.client.request(method, url, headers=headers, content=data)
            is_retryable = response.status_code == 429
            http_response = HttpResponse(
                status_code=response.status_code,
                content=response.content,
                headers=response.headers
            )
            return (is_retryable, http_response)
        except httpx.RequestError as e:
            raise

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        """Convenience method for GET requests."""
        retry_count = 0
        while retry_count < self.max_retries:
            is_retryable, response = self.request("GET", url, headers=headers)
            if not is_retryable:
                return response
            retry_count += 1
        raise httpx.RequestError(f"Max retries ({self.max_retries}) exceeded for 429", request=None)
