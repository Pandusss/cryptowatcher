"""
Фоновая задача для автоматического обновления кэша топ-3000 монет каждые 1 час
"""
import asyncio
from app.services.coingecko import CoinGeckoService


class CoinsCacheUpdater:
    """Класс для управления фоновым обновлением кэша монет"""
    
    def __init__(self):
        self.service = CoinGeckoService()
        self._running = False
        self._task = None
    
    async def start(self):
        """Запустить фоновую задачу обновления кэша"""
        if self._running:
            print("[CoinsCacheUpdater] Уже запущен")
            return
        
        self._running = True
        print("[CoinsCacheUpdater] Запуск фонового обновления кэша монет...")
        
        # Сразу обновляем кэш при старте
        await self.service.refresh_top3000_cache()
        
        # Запускаем периодическое обновление
        self._task = asyncio.create_task(self._update_loop())
        print("[CoinsCacheUpdater] Фоновая задача запущена, обновление каждые 1 час")
    
    async def _update_loop(self):
        """Цикл периодического обновления кэша"""
        while self._running:
            try:
                # Ждем 1 час (3600 секунд) перед следующим обновлением
                await asyncio.sleep(3600)
                
                if self._running:
                    print("[CoinsCacheUpdater] Начинаем плановое обновление кэша...")
                    await self.service.refresh_top3000_cache()
                    print("[CoinsCacheUpdater] Плановое обновление завершено")
                    
            except asyncio.CancelledError:
                print("[CoinsCacheUpdater] Задача отменена")
                break
            except Exception as e:
                print(f"[CoinsCacheUpdater] Ошибка в цикле обновления: {e}")
                # Продолжаем работу даже при ошибке
                await asyncio.sleep(60)  # Ждем 1 минуту перед повтором при ошибке
    
    def stop(self):
        """Остановить фоновую задачу"""
        if not self._running:
            return
        
        print("[CoinsCacheUpdater] Остановка фонового обновления кэша...")
        self._running = False
        
        if self._task:
            self._task.cancel()
            print("[CoinsCacheUpdater] Фоновая задача остановлена")


# Глобальный экземпляр для использования в приложении
coins_cache_updater = CoinsCacheUpdater()

