"""
Общий HTTP клиент для переиспользования в провайдерах

Предоставляет настроенный httpx.AsyncClient с общими параметрами.
"""
import httpx
from typing import Optional


class SharedHTTPClient:
    """Общий HTTP клиент для переиспользования"""
    
    _client: Optional[httpx.AsyncClient] = None
    
    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        """
        Получить общий HTTP клиент
        
        Returns:
            Настроенный httpx.AsyncClient
        """
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
        """Закрыть HTTP клиент"""
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None

