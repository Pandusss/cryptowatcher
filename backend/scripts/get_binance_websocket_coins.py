"""
Скрипт для получения списка всех монет, доступных через Binance WebSocket

WebSocket Binance использует символы в формате BTCUSDT, ETHUSDT и т.д.
Этот скрипт получает все активные торговые пары с Binance REST API.
"""
import asyncio
import httpx
import json
from pathlib import Path
from datetime import datetime


async def get_binance_websocket_coins():
    """Получить все активные торговые пары с Binance"""
    url = "https://api.binance.com/api/v3/exchangeInfo"
    
    print("🔄 Запрашиваем список торговых пар с Binance...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            symbols = data.get("symbols", [])
            print(f"✅ Получено {len(symbols)} торговых пар")
            
            # Фильтруем только активные пары
            active_symbols = [
                s for s in symbols 
                if s.get("status") == "TRADING"
            ]
            
            print(f"✅ Активных пар: {len(active_symbols)}")
            
            # Группируем по базовой валюте (quote asset)
            usdt_pairs = [s for s in active_symbols if s.get("quoteAsset") == "USDT"]
            btc_pairs = [s for s in active_symbols if s.get("quoteAsset") == "BTC"]
            busd_pairs = [s for s in active_symbols if s.get("quoteAsset") == "BUSD"]
            eth_pairs = [s for s in active_symbols if s.get("quoteAsset") == "ETH"]
            
            print(f"\n📊 Статистика по парам:")
            print(f"   USDT: {len(usdt_pairs)} пар")
            print(f"   BTC:  {len(btc_pairs)} пар")
            print(f"   BUSD: {len(busd_pairs)} пар")
            print(f"   ETH:  {len(eth_pairs)} пар")
            
            # Сохраняем все активные символы
            all_symbols = [s["symbol"] for s in active_symbols]
            
            # Сохраняем только USDT пары (самые популярные)
            usdt_symbols = [s["symbol"] for s in usdt_pairs]
            
            # Сохраняем в JSON с дополнительной информацией
            output_dir = Path(__file__).parent.parent
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 1. Все активные символы (простой список)
            all_symbols_file = output_dir / "binance_websocket_all_symbols.txt"
            with open(all_symbols_file, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(all_symbols)))
            print(f"\n💾 Сохранено: {all_symbols_file}")
            print(f"   Всего символов: {len(all_symbols)}")
            
            # 2. Только USDT пары (простой список)
            usdt_symbols_file = output_dir / "binance_websocket_usdt_symbols.txt"
            with open(usdt_symbols_file, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(usdt_symbols)))
            print(f"💾 Сохранено: {usdt_symbols_file}")
            print(f"   USDT пар: {len(usdt_symbols)}")
            
            # 3. Полная информация в JSON (только USDT)
            usdt_json_file = output_dir / "binance_websocket_usdt_pairs.json"
            usdt_data = {
                "timestamp": datetime.now().isoformat(),
                "total_pairs": len(usdt_pairs),
                "pairs": [
                    {
                        "symbol": s["symbol"],
                        "baseAsset": s["baseAsset"],
                        "quoteAsset": s["quoteAsset"],
                        "status": s["status"],
                        "permissions": s.get("permissions", []),
                    }
                    for s in sorted(usdt_pairs, key=lambda x: x["symbol"])
                ]
            }
            with open(usdt_json_file, "w", encoding="utf-8") as f:
                json.dump(usdt_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Сохранено: {usdt_json_file}")
            
            # 4. Полная информация в JSON (все активные пары)
            all_json_file = output_dir / "binance_websocket_all_pairs.json"
            all_data = {
                "timestamp": datetime.now().isoformat(),
                "total_pairs": len(active_symbols),
                "pairs_by_quote": {
                    "USDT": len(usdt_pairs),
                    "BTC": len(btc_pairs),
                    "BUSD": len(busd_pairs),
                    "ETH": len(eth_pairs),
                },
                "pairs": [
                    {
                        "symbol": s["symbol"],
                        "baseAsset": s["baseAsset"],
                        "quoteAsset": s["quoteAsset"],
                        "status": s["status"],
                        "permissions": s.get("permissions", []),
                    }
                    for s in sorted(active_symbols, key=lambda x: (x["quoteAsset"], x["symbol"]))
                ]
            }
            with open(all_json_file, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Сохранено: {all_json_file}")
            
            print(f"\n✅ Готово! Все файлы сохранены в: {output_dir}")
            print(f"\n📝 Формат символов для WebSocket:")
            print(f"   Пример: BTCUSDT, ETHUSDT, SOLUSDT")
            print(f"   WebSocket stream: wss://stream.binance.com:9443/ws/!ticker@arr")
            print(f"   (получает ВСЕ тикеры одним потоком)")
            
            return {
                "all_symbols": all_symbols,
                "usdt_symbols": usdt_symbols,
                "usdt_pairs": usdt_pairs,
                "all_pairs": active_symbols,
            }
            
        except httpx.HTTPError as e:
            print(f"❌ Ошибка HTTP: {e}")
            return None
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return None


if __name__ == "__main__":
    result = asyncio.run(get_binance_websocket_coins())
    if result:
        print(f"\n🎯 Краткая сводка:")
        print(f"   Всего символов: {len(result['all_symbols'])}")
        print(f"   USDT пар: {len(result['usdt_symbols'])}")
        print(f"\n💡 Для использования в WebSocket используйте символы из файлов:")
        print(f"   - binance_websocket_usdt_symbols.txt (только USDT пары)")
        print(f"   - binance_websocket_all_symbols.txt (все пары)")

