"""
Скрипт для маппинга монет из конфига на CoinGecko

Подход:
1. Загружаем ТОЛЬКО 2 запроса к CoinGecko:
   - /coins/markets (топ-250 монет с market_cap_rank)
   - /coins/list (полный список для fallback)
2. Все сравнения происходят ЛОКАЛЬНО, без дополнительных запросов
3. Жесткая проверка символов (точное совпадение буква в букву)
4. Выбираем самую популярную монету (по market_cap_rank)
5. Обновляем конфиг с CoinGecko ID

Запуск: python scripts/map_coins_from_coingecko_list.py
"""
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import httpx
from datetime import datetime

COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
CONFIG_FILE = Path(__file__).parent.parent / "app" / "core" / "configs" / "coins.json"
BACKUP_FILE = Path(__file__).parent.parent / "app" / "core" / "configs" / "coins.json.backup_coingecko_mapping"


def strict_symbol_match(our_symbol: str, coingecko_symbol: str) -> bool:
    """
    Жесткая проверка совпадения символов
    
    Правила:
    1. Оба символа приводятся к нижнему регистру
    2. Точное совпадение буква в букву
    3. Если длина разная - не проходит
    """
    our_lower = our_symbol.lower().strip()
    cg_lower = coingecko_symbol.lower().strip()
    
    return our_lower == cg_lower and len(our_lower) == len(cg_lower)


async def load_coingecko_markets() -> Dict[str, Tuple[str, int]]:
    """
    Загрузить топ монет из CoinGecko с market_cap_rank
    
    Использует /coins/markets чтобы получить монеты с рейтингом популярности
    
    Returns:
        Словарь {symbol_lower: (coin_id, market_cap_rank)}
        Только самая популярная монета для каждого символа
    """
    print("[CoinGecko] Загружаем топ монет из /coins/markets...")
    
    symbol_to_best_coin = {}
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Загружаем топ-250 монет (максимум за один запрос)
            # Это покроет большинство популярных монет
            response = await client.get(
                f"{COINGECKO_API_URL}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 250,
                    "page": 1,
                    "sparkline": False
                }
            )
            response.raise_for_status()
            markets = response.json()
            
            # Создаем словарь: symbol (lowercase) -> (coin_id, market_cap_rank)
            # Если несколько монет с одним символом - берем самую популярную (меньший rank)
            for coin in markets:
                symbol = coin.get("symbol", "").lower().strip()
                coin_id = coin.get("id", "")
                market_cap_rank = coin.get("market_cap_rank")
                
                if symbol and coin_id and market_cap_rank is not None:
                    # Если символ уже есть, сравниваем по rank (меньше = популярнее)
                    if symbol not in symbol_to_best_coin:
                        symbol_to_best_coin[symbol] = (coin_id, market_cap_rank)
                    else:
                        existing_rank = symbol_to_best_coin[symbol][1]
                        if market_cap_rank < existing_rank:
                            symbol_to_best_coin[symbol] = (coin_id, market_cap_rank)
            
            print(f"[CoinGecko] ✅ Загружено {len(markets)} монет из топ-250")
            print(f"[CoinGecko] ✅ Уникальных символов: {len(symbol_to_best_coin)}")
            
            return symbol_to_best_coin
            
    except Exception as e:
        print(f"[CoinGecko] ❌ Ошибка при загрузке: {e}")
        return {}


async def load_coingecko_coins_list() -> Dict[str, List[str]]:
    """
    Загрузить полный список монет из CoinGecko (fallback для непопулярных монет)
    
    Returns:
        Словарь {symbol_lower: [coin_id1, coin_id2, ...]}
    """
    print("[CoinGecko] Загружаем полный список монет из /coins/list (fallback)...")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(f"{COINGECKO_API_URL}/coins/list")
            response.raise_for_status()
            coins_list = response.json()
            
            symbol_to_ids = {}
            for coin in coins_list:
                symbol = coin.get("symbol", "").lower().strip()
                coin_id = coin.get("id", "")
                
                if symbol and coin_id:
                    if symbol not in symbol_to_ids:
                        symbol_to_ids[symbol] = []
                    symbol_to_ids[symbol].append(coin_id)
            
            print(f"[CoinGecko] ✅ Загружено {len(coins_list)} монет")
            print(f"[CoinGecko] ✅ Уникальных символов: {len(symbol_to_ids)}")
            
            return symbol_to_ids
            
    except Exception as e:
        print(f"[CoinGecko] ❌ Ошибка при загрузке списка: {e}")
        return {}


def find_best_coingecko_coin(symbol: str, markets_dict: Dict[str, Tuple[str, int]], list_dict: Dict[str, List[str]]) -> Optional[Tuple[str, int]]:
    """
    Найти лучшую монету в CoinGecko для символа (локальное сравнение, БЕЗ запросов)
    
    Args:
        symbol: Символ монеты из конфига
        markets_dict: Словарь из /coins/markets {symbol: (coin_id, rank)}
        list_dict: Словарь из /coins/list {symbol: [coin_id1, coin_id2, ...]} (fallback)
        
    Returns:
        (coin_id, market_cap_rank) или None
    """
    symbol_lower = symbol.lower().strip()
    
    # Сначала проверяем в markets (там есть rank, и это популярные монеты)
    if symbol_lower in markets_dict:
        coin_id, rank = markets_dict[symbol_lower]
        return (coin_id, rank)
    
    # Если не нашли в markets, проверяем в полном списке (fallback)
    # Но там нет rank, поэтому берем первую монету
    if symbol_lower in list_dict:
        coin_ids = list_dict[symbol_lower]
        if coin_ids:
            # Берем первую монету (обычно это основная)
            return (coin_ids[0], 999999)  # Ранк неизвестен, ставим большое число
    
    return None


def load_config() -> Dict:
    """Загрузить текущий конфиг"""
    if not CONFIG_FILE.exists():
        print(f"❌ Файл конфига не найден: {CONFIG_FILE}")
        return {}
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                print(f"⚠️  Конфиг пустой")
                return {}
            return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка чтения конфига: {e}")
        return {}


def save_config(config: Dict, backup: bool = True):
    """Сохранить конфиг"""
    if backup and CONFIG_FILE.exists():
        import shutil
        shutil.copy2(CONFIG_FILE, BACKUP_FILE)
        print(f"\n✅ Создан бэкап: {BACKUP_FILE}")
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Конфиг сохранен: {CONFIG_FILE}")


def map_all_coins(config: Dict, markets_dict: Dict[str, Tuple[str, int]], list_dict: Dict[str, List[str]]) -> Dict:
    """
    Маппинг всех монет из конфига на CoinGecko
    
    Returns:
        Статистика маппинга
    """
    coins = config.get("coins", {})
    
    if not coins:
        print("❌ В конфиге нет монет")
        return {"mapped": 0, "updated": 0, "not_found": [], "skipped": 0, "total": 0}
    
    print(f"\n[Маппинг] Обрабатываем {len(coins)} монет...")
    print("=" * 80)
    
    mapped_count = 0
    updated_count = 0
    skipped_count = 0
    not_found = []
    
    for i, (coin_id, coin_data) in enumerate(coins.items(), 1):
        symbol = coin_data.get("symbol", "")
        if not symbol:
            print(f"  {i:3d}. {coin_id:15s} | ⚠️  Нет символа, пропускаем")
            skipped_count += 1
            continue
        
        # Проверяем, есть ли уже CoinGecko ID
        external_ids = coin_data.get("external_ids", {})
        existing_coingecko_id = external_ids.get("coingecko", "")
        
        print(f"  {i:3d}. {symbol:10s} ({coin_id:15s}) | ", end="", flush=True)
        
        # Ищем лучшую монету в CoinGecko (локальное сравнение, БЕЗ запросов)
        result = find_best_coingecko_coin(symbol, markets_dict, list_dict)
        
        if result:
            coingecko_id, rank = result
            
            # Добавляем/обновляем в external_ids
            if "external_ids" not in coin_data:
                coin_data["external_ids"] = {}
            
            if existing_coingecko_id:
                if existing_coingecko_id != coingecko_id:
                    coin_data["external_ids"]["coingecko"] = coingecko_id
                    rank_str = f"rank: {rank}" if rank < 999999 else "rank: неизвестен"
                    print(f"✅ Обновлено: {existing_coingecko_id} → {coingecko_id} ({rank_str})")
                    updated_count += 1
                else:
                    rank_str = f"rank: {rank}" if rank < 999999 else "rank: неизвестен"
                    print(f"✅ Уже есть: {coingecko_id} ({rank_str})")
                    mapped_count += 1
            else:
                coin_data["external_ids"]["coingecko"] = coingecko_id
                rank_str = f"rank: {rank}" if rank < 999999 else "rank: неизвестен"
                print(f"✅ Найдено: {coingecko_id} ({rank_str})")
                mapped_count += 1
        else:
            print(f"❌ Не найдено")
            not_found.append((symbol, coin_id))
    
    return {
        "mapped": mapped_count,
        "updated": updated_count,
        "not_found": not_found,
        "skipped": skipped_count,
        "total": len(coins)
    }


async def main():
    """Основная функция"""
    print("=" * 80)
    print("МАППИНГ МОНЕТ ИЗ КОНФИГА НА COINGECKO")
    print("=" * 80)
    print(f"\nДата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n⚠️  Внимание:")
    print("   - Скрипт делает ТОЛЬКО 2 запроса к CoinGecko:")
    print("     1. /coins/markets (топ-250 монет с рейтингом)")
    print("     2. /coins/list (полный список для fallback)")
    print("   - Все сравнения происходят локально, БЕЗ дополнительных запросов")
    print("   - Обработка 100 монет займет ~1 минуту")
    print()
    
    # Загружаем конфиг
    print(f"[Загрузка] Читаем конфиг из {CONFIG_FILE}...")
    config = load_config()
    
    if not config or "coins" not in config:
        print("❌ Не удалось загрузить конфиг")
        return
    
    coins = config.get("coins", {})
    if not coins:
        print("❌ В конфиге нет монет")
        return
    
    print(f"✅ В конфиге {len(coins)} монет")
    
    # Загружаем данные из CoinGecko (только 2 запроса!)
    print("\n[Загрузка] Загружаем данные из CoinGecko...")
    markets_dict = await load_coingecko_markets()
    list_dict = await load_coingecko_coins_list()
    
    if not markets_dict and not list_dict:
        print("❌ Не удалось загрузить данные из CoinGecko")
        return
    
    print(f"\n✅ Данные загружены:")
    print(f"   - Топ монет с рейтингом: {len(markets_dict)}")
    print(f"   - Полный список (fallback): {len(list_dict)}")
    
    # Подтверждение
    print(f"\n⚠️  Будет обработано {len(coins)} монет")
    print(f"   Примерное время: ~1 минута (только загрузка данных, сравнение мгновенное)")
    print(f"\nНажмите Enter для продолжения или Ctrl+C для отмены...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n❌ Отменено пользователем")
        return
    
    # Маппинг (локальное сравнение, БЕЗ дополнительных запросов)
    stats = map_all_coins(config, markets_dict, list_dict)
    
    # Сохраняем конфиг
    print(f"\n[Сохранение] Сохраняем обновленный конфиг...")
    save_config(config, backup=True)
    
    # Статистика
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    print(f"Всего монет в конфиге: {stats['total']}")
    print(f"Найдено/обновлено в CoinGecko: {stats['mapped'] + stats['updated']}")
    print(f"  - Новых: {stats['mapped']}")
    print(f"  - Обновлено: {stats['updated']}")
    print(f"Пропущено (нет символа): {stats['skipped']}")
    print(f"Не найдено: {len(stats['not_found'])}")
    
    if stats['not_found']:
        print(f"\n⚠️  Монеты, которые не найдены в CoinGecko:")
        for symbol, coin_id in stats['not_found'][:20]:  # Показываем первые 20
            print(f"  - {symbol:10s} (ID: {coin_id})")
        if len(stats['not_found']) > 20:
            print(f"  ... и еще {len(stats['not_found']) - 20}")
    
    print("=" * 80)
    print("✅ Готово!")
    print(f"📄 Бэкап: {BACKUP_FILE}")
    print(f"📄 Конфиг: {CONFIG_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

