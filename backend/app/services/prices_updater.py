"""
Фоновая задача для автоматического обновления цен монет каждые 10 секунд
"""
import asyncio
import json
from app.services.coingecko import CoinGeckoService
from app.core.redis_client import get_redis

# Константы
UPDATE_INTERVAL_SECONDS = 10  # 10 секунд
ERROR_RETRY_DELAY_SECONDS = 5  # 5 секунд при ошибке


class PricesUpdater:
    """Класс для управления фоновым обновлением цен монет"""
    
    def __init__(self):
        self.service = CoinGeckoService()
        self._running = False
        self._task = None
    
    async def start(self):
        """Запустить фоновую задачу обновления цен"""
        if self._running:
            print("[PricesUpdater] Уже запущен")
            return
        
        self._running = True
        print("[PricesUpdater] 🚀 Запуск фонового обновления цен монет каждые 10 секунд...")
        
        # Сразу обновляем цены при старте
        await self._update_prices()
        
        # Запускаем периодическое обновление
        self._task = asyncio.create_task(self._update_loop())
        print("[PricesUpdater] ✅ Фоновая задача запущена, обновление каждые 10 секунд")
    
    async def _update_prices(self):
        """Обновить цены всех монет из конфига"""
        try:
            # Загружаем список монет из конфига
            config_coins, _ = self.service._load_coins_config()
            
            if not config_coins:
                print("[PricesUpdater] ⚠️ Конфиг-файл пустой, пропускаем обновление")
                return
            
            print(f"[PricesUpdater] Обновление цен для {len(config_coins)} монет...")
            
            # Получаем цены через batch API
            batch_prices = await self.service.get_batch_prices(config_coins)
            
            # Сохраняем цены в Redis кэш
            redis = await get_redis()
            if redis:
                updated_count = 0
                for coin_id, price_info in batch_prices.items():
                    try:
                        price = price_info.get('usd', 0)
                        if price > 0:
                            price_data = {
                                "price": price,
                                "percent_change_24h": price_info.get('usd_24h_change', 0),
                                "volume_24h": price_info.get('usd_24h_vol', 0),
                                "priceDecimals": self.service.get_price_decimals(price),
                            }
                            price_cache_key = f"coin_price:{coin_id}"
                            await redis.setex(
                                price_cache_key, 
                                self.service.CACHE_TTL_COIN_PRICE, 
                                json.dumps(price_data)
                            )
                            updated_count += 1
                    except Exception as e:
                        print(f"[PricesUpdater] Ошибка при сохранении цены для {coin_id}: {e}")
                
                print(f"[PricesUpdater] ✅ Обновлено цен: {updated_count} из {len(config_coins)} монет")
            else:
                print("[PricesUpdater] ⚠️ Redis недоступен, цены не кэшируются")
                
        except Exception as e:
            print(f"[PricesUpdater] ❌ Ошибка при обновлении цен: {e}")
            import traceback
            print(f"[PricesUpdater] Traceback: {traceback.format_exc()}")
    
    async def _update_loop(self):
        """Цикл периодического обновления цен"""
        while self._running:
            try:
                # Ждем 10 секунд перед следующим обновлением
                await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
                
                if self._running:
                    await self._update_prices()
                    
            except asyncio.CancelledError:
                print("[PricesUpdater] Задача отменена")
                break
            except Exception as e:
                print(f"[PricesUpdater] Ошибка в цикле обновления: {e}")
                # Продолжаем работу даже при ошибке, ждем меньше времени
                await asyncio.sleep(ERROR_RETRY_DELAY_SECONDS)
    
    def stop(self):
        """Остановить фоновую задачу"""
        if not self._running:
            return
        
        print("[PricesUpdater] ⏹️ Остановка фонового обновления цен...")
        self._running = False
        
        if self._task:
            self._task.cancel()
            print("[PricesUpdater] Фоновая задача остановлена")


# Глобальный экземпляр для использования в приложении
prices_updater = PricesUpdater()

