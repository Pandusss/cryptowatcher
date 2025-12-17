"""
CoinGecko HTTP Client

HTTP client for working with CoinGecko API.
"""
import asyncio
import httpx
import logging
from typing import Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger(f"CoingeckoCLient")

class CoinGeckoClient:    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    def __init__(self):
        self.headers = {"Accept": "application/json"}
        
        self.api_key = getattr(settings, 'COINGECKO_API_KEY', '') or ''
        if self.api_key:
            self.headers["x-cg-demo-api-key"] = self.api_key
        
        # HTTP client is created lazily on first request
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=30.0
            )
        return self._client
    
    async def close(self):
        """Close HTTP client"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def get(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        retry_on_rate_limit: bool = True
    ) -> Dict:
        url = f"{self.BASE_URL}{endpoint}"
        client = await self._get_client()
        
        try:
            response = await client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and retry_on_rate_limit:
                # Rate limit - wait and retry
                retry_after = int(e.response.headers.get("Retry-After", "60"))
                await asyncio.sleep(retry_after)
                return await self.get(endpoint, params, retry_on_rate_limit=False)
            
            raise
        
        except Exception as e:
            logger.error(f"Request error to {url}: {e}")
            raise