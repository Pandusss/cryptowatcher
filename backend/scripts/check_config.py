"""Проверка конфига"""
import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "app" / "core" / "configs" / "coins.json"

with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    config = json.load(f)

coins = config['coins']
total = len(coins)

print("=" * 60)
print("ПРОВЕРКА КОНФИГА")
print("=" * 60)
print(f"\nВсего монет: {total}")
print(f"Ожидалось: 100")
print(f"{'✅ Количество совпадает!' if total == 100 else '⚠️ Количество не совпадает!'}")

with_binance = sum(1 for c in coins.values() if c.get("external_ids", {}).get("binance"))
enabled = sum(1 for c in coins.values() if c.get("enabled"))

print(f"\nМонет с Binance маппингом: {with_binance} из {total}")
print(f"Включенных монет: {enabled} из {total}")

print(f"\nТоп-10 монет:")
for i, (coin_id, coin_data) in enumerate(list(coins.items())[:10], 1):
    symbol = coin_data.get("symbol", "")
    binance = coin_data.get("external_ids", {}).get("binance", "")
    print(f"  {i:2d}. {coin_id:15s} - {symbol:10s} - {binance}")

print(f"\nПоследние 5 монет:")
for i, (coin_id, coin_data) in enumerate(list(coins.items())[-5:], total - 4):
    symbol = coin_data.get("symbol", "")
    binance = coin_data.get("external_ids", {}).get("binance", "")
    print(f"  {i:2d}. {coin_id:15s} - {symbol:10s} - {binance}")

print("\n" + "=" * 60)
