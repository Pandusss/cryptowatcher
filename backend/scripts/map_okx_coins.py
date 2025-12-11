"""
Скрипт для маппинга монет из конфига на OKX

Подход:
1. Загружаем список монет с OKX API (SPOT пары)
2. Для каждой монеты в coins.json:
   - Берем символ из CoinGecko (external_ids["coingecko"])
   - Получаем символ CoinGecko через API для точного совпадения
   - Ищем этот символ в OKX монетах (по baseCcy)
   - Если найдено точное совпадение - добавляем OKX символ (instId) в external_ids["okx"]
3. Жесткая проверка символов (точное совпадение буква в букву)

Запуск: python scripts/map_okx_coins.py
"""
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import httpx
from datetime import datetime

OKX_API_URL = "https://www.okx.com/api/v5/public/instruments"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
CONFIG_FILE = Path(__file__).parent.parent / "app" / "core" / "configs" / "coins.json"
BACKUP_FILE = Path(__file__).parent.parent / "app" / "core" / "configs" / "coins.json.backup_okx_mapping"


def strict_symbol_match(our_symbol: str, okx_symbol: str) -> bool:
    """
    Жесткая проверка совпадения символов
    
    Правила:
    1. Оба символа приводятся к верхнему регистру
    2. Точное совпадение буква в букву
    3. Если длина разная - не проходит
    """
    our_upper = our_symbol.upper().strip()
    okx_upper = okx_symbol.upper().strip()
    
    return our_upper == okx_upper and len(our_upper) == len(okx_upper)


async def load_okx_instruments() -> Dict[str, Dict]:
    """
    Загрузить список инструментов с OKX
    
    Returns:
        Словарь {baseCcy_upper: {instId, baseCcy, quoteCcy, ...}}
        Только USDT пары для точности
    """
    print("[OKX] Загружаем список инструментов с OKX API...")
    
    base_to_okx = {}
    
    try:
        async with httpx.AsyncClient(
            timeout=60.0,
            verify=True,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        ) as client:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            response = await client.get(
                OKX_API_URL,
                params={"instType": "SPOT"},
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != "0":
                print(f"❌ Ошибка API OKX: {data.get('msg', 'Unknown error')}")
                return {}
            
            instruments = data.get("data", [])
            print(f"[OKX] ✅ Получено {len(instruments)} инструментов")
            
            # Фильтруем только активные USDT пары
            active_usdt_pairs = [
                inst for inst in instruments
                if inst.get("state") == "live" and inst.get("quoteCcy") == "USDT"
            ]
            
            print(f"[OKX] ✅ Активных USDT пар: {len(active_usdt_pairs)}")
            
            # Создаем словарь: baseCcy (uppercase) -> {instId, baseCcy, quoteCcy, ...}
            # Если несколько пар с одним baseCcy - берем первую (обычно это основная)
            for inst in active_usdt_pairs:
                base_ccy = inst.get("baseCcy", "").upper().strip()
                if base_ccy and base_ccy not in base_to_okx:
                    base_to_okx[base_ccy] = {
                        "instId": inst.get("instId", ""),
                        "baseCcy": inst.get("baseCcy", ""),
                        "quoteCcy": inst.get("quoteCcy", ""),
                        "state": inst.get("state", ""),
                    }
            
            print(f"[OKX] ✅ Уникальных базовых валют: {len(base_to_okx)}")
            
            return base_to_okx
            
    except httpx.HTTPError as e:
        print(f"[OKX] ❌ Ошибка HTTP: {e}")
        return {}
    except Exception as e:
        print(f"[OKX] ❌ Ошибка при загрузке: {e}")
        import traceback
        traceback.print_exc()
        return {}


async def load_coingecko_symbols() -> Dict[str, str]:
    """
    Загрузить символы монет из CoinGecko по их ID
    
    Returns:
        Словарь {coingecko_id: symbol_upper}
    """
    print("[CoinGecko] Загружаем символы монет из CoinGecko...")
    
    id_to_symbol = {}
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Загружаем полный список монет
            response = await client.get(f"{COINGECKO_API_URL}/coins/list")
            response.raise_for_status()
            coins_list = response.json()
            
            for coin in coins_list:
                coin_id = coin.get("id", "")
                symbol = coin.get("symbol", "").upper().strip()
                
                if coin_id and symbol:
                    id_to_symbol[coin_id] = symbol
            
            print(f"[CoinGecko] ✅ Загружено {len(id_to_symbol)} монет")
            
            return id_to_symbol
            
    except Exception as e:
        print(f"[CoinGecko] ❌ Ошибка при загрузке: {e}")
        return {}


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


def map_all_coins(
    config: Dict,
    okx_dict: Dict[str, Dict],
    coingecko_symbols: Dict[str, str]
) -> Dict:
    """
    Маппинг всех монет из конфига на OKX
    
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
        # Проверяем, есть ли CoinGecko ID
        external_ids = coin_data.get("external_ids", {})
        coingecko_id = external_ids.get("coingecko", "")
        
        if not coingecko_id:
            print(f"  {i:3d}. {coin_data.get('symbol', ''):10s} ({coin_id:15s}) | ⚠️  Нет CoinGecko ID, пропускаем")
            skipped_count += 1
            continue
        
        # Получаем символ из CoinGecko
        cg_symbol = coingecko_symbols.get(coingecko_id, "")
        if not cg_symbol:
            print(f"  {i:3d}. {coin_data.get('symbol', ''):10s} ({coin_id:15s}) | ⚠️  Не найден символ CoinGecko для {coingecko_id}")
            skipped_count += 1
            continue
        
        print(f"  {i:3d}. {cg_symbol:10s} ({coin_id:15s}) | ", end="", flush=True)
        
        # Ищем в OKX по baseCcy (жесткое совпадение символов)
        okx_info = okx_dict.get(cg_symbol.upper())
        
        if okx_info:
            okx_inst_id = okx_info["instId"]
            
            # Добавляем/обновляем в external_ids
            if "external_ids" not in coin_data:
                coin_data["external_ids"] = {}
            
            existing_okx_id = external_ids.get("okx", "")
            
            if existing_okx_id:
                if existing_okx_id != okx_inst_id:
                    coin_data["external_ids"]["okx"] = okx_inst_id
                    print(f"✅ Обновлено: {existing_okx_id} → {okx_inst_id}")
                    updated_count += 1
                else:
                    print(f"✅ Уже есть: {okx_inst_id}")
                    mapped_count += 1
            else:
                coin_data["external_ids"]["okx"] = okx_inst_id
                print(f"✅ Найдено: {okx_inst_id}")
                mapped_count += 1
        else:
            print(f"❌ Не найдено в OKX")
            not_found.append((cg_symbol, coin_id, coingecko_id))
    
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
    print("МАППИНГ МОНЕТ ИЗ КОНФИГА НА OKX")
    print("=" * 80)
    print(f"\nДата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n⚠️  Внимание:")
    print("   - Скрипт делает запросы к OKX API и CoinGecko API")
    print("   - Жесткая проверка символов (точное совпадение)")
    print("   - Добавляет только USDT пары из OKX")
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
    
    # Загружаем данные из OKX и CoinGecko
    print("\n[Загрузка] Загружаем данные из OKX и CoinGecko...")
    okx_dict = await load_okx_instruments()
    coingecko_symbols = await load_coingecko_symbols()
    
    if not okx_dict:
        print("❌ Не удалось загрузить данные из OKX")
        return
    
    if not coingecko_symbols:
        print("❌ Не удалось загрузить данные из CoinGecko")
        return
    
    print(f"\n✅ Данные загружены:")
    print(f"   - OKX инструментов: {len(okx_dict)}")
    print(f"   - CoinGecko монет: {len(coingecko_symbols)}")
    
    # Подтверждение
    print(f"\n⚠️  Будет обработано {len(coins)} монет")
    print(f"\nНажмите Enter для продолжения или Ctrl+C для отмены...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n❌ Отменено пользователем")
        return
    
    # Маппинг
    stats = map_all_coins(config, okx_dict, coingecko_symbols)
    
    # Сохраняем конфиг
    print(f"\n[Сохранение] Сохраняем обновленный конфиг...")
    save_config(config, backup=True)
    
    # Статистика
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    print(f"Всего монет в конфиге: {stats['total']}")
    print(f"Найдено/обновлено в OKX: {stats['mapped'] + stats['updated']}")
    print(f"  - Новых: {stats['mapped']}")
    print(f"  - Обновлено: {stats['updated']}")
    print(f"Пропущено (нет CoinGecko ID или символа): {stats['skipped']}")
    print(f"Не найдено в OKX: {len(stats['not_found'])}")
    
    if stats['not_found']:
        print(f"\n⚠️  Монеты, которые не найдены в OKX:")
        for symbol, coin_id, cg_id in stats['not_found'][:20]:  # Показываем первые 20
            print(f"  - {symbol:10s} (ID: {coin_id}, CG: {cg_id})")
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

