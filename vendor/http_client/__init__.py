import aiohttp
import asyncio
from typing import Any, Dict

class HttpClient:
    """Asynchronous HTTP client for making API requests."""
    def __init__(self) -> None:
        self.session: aiohttp.ClientSession = None

    async def get(self, url: str, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Make an asynchronous GET request.

        Args:
            url: The URL to request.
            headers: Optional headers for the request.

        Returns:
            dict: JSON response.

        Raises:
            aiohttp.ClientError: If the request fails.
        """
        if self.session is None:
            self.session = aiohttp.ClientSession()
        try:
            async with self.session.get(url, headers=headers or {}) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise aiohttp.ClientError(f"HTTP request failed: {str(e)}")

    async def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

