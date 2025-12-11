"""
CoinGecko HTTP Client

HTTP клиент для работы с CoinGecko API.
"""
import asyncio
import httpx
from typing import Dict, Any, Optional

from app.core.config import settings


class CoinGeckoClient:
    """HTTP клиент для работы с CoinGecko API"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    def __init__(self):
        self.headers = {"Accept": "application/json"}
        
        # Добавляем API ключ, если он есть
        self.api_key = getattr(settings, 'COINGECKO_API_KEY', '') or ''
        if self.api_key:
            self.headers["x-cg-demo-api-key"] = self.api_key
        
        # HTTP клиент создается лениво при первом запросе
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Получить или создать HTTP клиент"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=30.0
            )
        return self._client
    
    async def close(self):
        """Закрыть HTTP клиент"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def get(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        retry_on_rate_limit: bool = True
    ) -> Dict:
        """
        Выполнить GET запрос к CoinGecko API
        
        Args:
            endpoint: URL эндпоинта (например, "/coins/markets")
            params: Параметры запроса
            retry_on_rate_limit: Повторить запрос при rate limit
            
        Returns:
            Ответ API в формате JSON
        """
        url = f"{self.BASE_URL}{endpoint}"
        client = await self._get_client()
        
        try:
            response = await client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and retry_on_rate_limit:
                # Rate limit - ждем и повторяем
                retry_after = int(e.response.headers.get("Retry-After", "60"))
                print(f"[CoinGeckoClient] Rate limit, ждем {retry_after} секунд...")
                await asyncio.sleep(retry_after)
                return await self.get(endpoint, params, retry_on_rate_limit=False)
            
            raise
        
        except Exception as e:
            print(f"[CoinGeckoClient] Ошибка запроса к {url}: {e}")
            raise

