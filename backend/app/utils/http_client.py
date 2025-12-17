"""
General HTTP client for reuse in providers

Provides a configured httpx.AsyncClient with common parameters.
"""
import httpx
from typing import Optional


class SharedHTTPClient:
    
    _client: Optional[httpx.AsyncClient] = None
    
    @classmethod
    def get_client(cls) -> httpx.AsyncClient:

        if cls._client is None:
            cls._client = httpx.AsyncClient(
                timeout=30.0,
                verify=True,
                follow_redirects=True,
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10
                ),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "CryptoWatcher/1.0",
                }
            )
        return cls._client
    
    @classmethod
    async def close(cls):
        
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None

