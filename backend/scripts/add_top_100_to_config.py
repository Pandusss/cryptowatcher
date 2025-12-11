"""
Скрипт для добавления топ-100 монет по объему торгов в coins.json

Читает binance_top_by_volume.json и добавляет топ-100 монет в конфиг.
"""
import json
from pathlib import Path
from typing import Dict, List


# Пути к файлам
CONFIG_FILE = Path(__file__).parent.parent / "app" / "core" / "configs" / "coins.json"
BACKUP_FILE = Path(__file__).parent.parent / "app" / "core" / "configs" / "coins.json.backup_top100"
TOP_VOLUME_FILE = Path(__file__).parent.parent / "binance_top_by_volume.json"


def load_top_volume() -> List[Dict]:
    """Загрузить топ-200 по объему"""
    with open(TOP_VOLUME_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get("top_200_by_volume", [])


def load_config() -> Dict:
    """Загрузить текущий конфиг или создать новый"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    # Файл пустой
                    print("  ⚠️  Конфиг пустой, создаем новый")
                    return {
                        "version": "1.0",
                        "coins": {}
                    }
                config = json.loads(content)
                if "coins" not in config:
                    config["coins"] = {}
                return config
        except json.JSONDecodeError:
            # Файл поврежден или пустой
            print("  ⚠️  Конфиг поврежден или пустой, создаем новый")
            return {
                "version": "1.0",
                "coins": {}
            }
    else:
        # Создаем новый конфиг
        return {
            "version": "1.0",
            "coins": {}
        }


def save_config(config: Dict, backup: bool = True):
    """Сохранить конфиг"""
    if backup and CONFIG_FILE.exists():
        # Создаем бэкап
        import shutil
        shutil.copy2(CONFIG_FILE, BACKUP_FILE)
        print(f"✅ Создан бэкап: {BACKUP_FILE}")
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Конфиг сохранен: {CONFIG_FILE}")


def generate_coin_id(base_symbol: str) -> str:
    """
    Сгенерировать внутренний ID монеты
    
    Использует base_symbol в нижнем регистре как ID
    """
    return base_symbol.lower()


def create_coin_entry(base_symbol: str, binance_symbol: str) -> Dict:
    """
    Создать новую запись монеты в конфиге
    
    Args:
        base_symbol: Символ монеты (например, "BTC")
        binance_symbol: Полный символ пары (например, "BTCUSDT")
        
    Returns:
        Словарь с данными монеты
    """
    coin_id = generate_coin_id(base_symbol)
    
    return {
        "id": coin_id,
        "name": base_symbol,  # Базовое название, можно обновить позже из CoinGecko
        "symbol": base_symbol,
        "enabled": True,
        "external_ids": {
            "binance": binance_symbol
        },
        "price_priority": ["binance"]
    }


def main():
    """Основная функция"""
    print("=" * 80)
    print("ДОБАВЛЕНИЕ ТОП-100 МОНЕТ ПО ОБЪЕМУ В КОНФИГ")
    print("=" * 80)
    
    # Проверяем наличие файла с топ-200
    if not TOP_VOLUME_FILE.exists():
        print(f"❌ Файл не найден: {TOP_VOLUME_FILE}")
        print(f"   Запустите сначала: python scripts/get_binance_top_by_volume.py")
        return
    
    # Загружаем топ-200 и берем первые 100
    print(f"\n[Загрузка] Читаем топ-200 из {TOP_VOLUME_FILE}...")
    top_200 = load_top_volume()
    
    if not top_200:
        print("❌ Не найдены данные топ-200")
        return
    
    # Берем топ-100
    top_100 = top_200[:100]
    print(f"✅ Загружено {len(top_100)} монет из топ-100")
    
    # Загружаем текущий конфиг
    print(f"\n[Загрузка] Читаем текущий конфиг из {CONFIG_FILE}...")
    config = load_config()
    coins = config["coins"]
    initial_count = len(coins)
    
    print(f"✅ В конфиге сейчас {initial_count} монет")
    
    # Обрабатываем каждую монету из топ-100
    print(f"\n[Обработка] Добавляем монеты из топ-100...")
    
    added_count = 0
    updated_count = 0
    skipped_count = 0
    
    for i, pair_data in enumerate(top_100, 1):
        base_symbol = pair_data.get("base_symbol", "")
        binance_symbol = pair_data.get("symbol", "")
        
        if not base_symbol or not binance_symbol:
            print(f"  ⚠️  Пропущена запись #{i}: нет символа")
            skipped_count += 1
            continue
        
        # Генерируем ID
        coin_id = generate_coin_id(base_symbol)
        
        if coin_id in coins:
            # Монета уже есть - обновляем
            print(f"  {i:3d}. {base_symbol:12s} | Обновляем существующую монету (ID: {coin_id})")
            
            coin_data = coins[coin_id]
            
            # Обновляем external_ids
            if "external_ids" not in coin_data:
                coin_data["external_ids"] = {}
            
            if "binance" not in coin_data["external_ids"]:
                coin_data["external_ids"]["binance"] = binance_symbol
                print(f"      ➕ Добавлен Binance маппинг: {binance_symbol}")
            
            # Обновляем price_priority
            if "price_priority" not in coin_data:
                coin_data["price_priority"] = []
            
            if "binance" not in coin_data["price_priority"]:
                coin_data["price_priority"].insert(0, "binance")
                print(f"      ➕ Добавлен Binance в price_priority")
            
            # Убеждаемся что монета включена
            if not coin_data.get("enabled", False):
                coin_data["enabled"] = True
                print(f"      ✅ Монета включена")
            
            updated_count += 1
        else:
            # Новая монета - создаем запись
            print(f"  {i:3d}. {base_symbol:12s} | ➕ Добавляем новую монету (ID: {coin_id})")
            coins[coin_id] = create_coin_entry(base_symbol, binance_symbol)
            added_count += 1
    
    # Сохраняем конфиг
    print(f"\n[Сохранение] Сохраняем обновленный конфиг...")
    save_config(config, backup=True)
    
    # Статистика
    final_count = len(coins)
    
    print("\n" + "=" * 80)
    print("СТАТИСТИКА")
    print("=" * 80)
    print(f"Монет в конфиге до: {initial_count}")
    print(f"Монет в конфиге после: {final_count}")
    print(f"Добавлено новых: {added_count}")
    print(f"Обновлено существующих: {updated_count}")
    print(f"Пропущено: {skipped_count}")
    print(f"Всего обработано: {len(top_100)}")
    print("=" * 80)
    
    # Проверяем топ-10
    print("\n[Проверка] Топ-10 монет из топ-100:")
    for i, pair_data in enumerate(top_100[:10], 1):
        base_symbol = pair_data.get("base_symbol", "")
        binance_symbol = pair_data.get("symbol", "")
        coin_id = generate_coin_id(base_symbol)
        
        if coin_id in coins:
            coin_data = coins[coin_id]
            binance_mapping = coin_data.get("external_ids", {}).get("binance", "❌")
            status = "✅ В конфиге" if binance_mapping == binance_symbol else "⚠️ Не совпадает"
            print(f"  {i:2d}. {base_symbol:12s} ({binance_symbol}) - {status}")
        else:
            print(f"  {i:2d}. {base_symbol:12s} ({binance_symbol}) - ❌ Не найдена")
    
    print("\n✅ Готово!")
    print(f"📄 Бэкап: {BACKUP_FILE}")
    print(f"📄 Конфиг: {CONFIG_FILE}")


if __name__ == "__main__":
    main()

