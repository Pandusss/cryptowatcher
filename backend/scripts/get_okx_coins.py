"""
Скрипт для получения списка всех монет, доступных через OKX WebSocket

OKX WebSocket использует символы в формате BTC-USDT, ETH-USDT и т.д.
Этот скрипт получает все активные торговые пары с OKX REST API.
"""
import asyncio
import httpx
import json
from pathlib import Path
from datetime import datetime


async def get_okx_coins():
    """Получить все активные торговые пары с OKX"""
    # Правильный URL для OKX API v5
    url = "https://www.okx.com/api/v5/public/instruments"
    
    print("🔄 Запрашиваем список торговых пар с OKX...")
    print(f"   URL: {url}")
    print(f"   Параметры: instType=SPOT")
    
    async with httpx.AsyncClient(
        timeout=30.0,
        verify=True,
        follow_redirects=True,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    ) as client:
        try:
            # OKX API требует параметр instType для типа инструмента
            # SPOT - спотовые пары
            # Также требуется заголовок Accept
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            print(f"[DEBUG] Отправляем запрос...")
            response = await client.get(url, params={"instType": "SPOT"}, headers=headers)
            print(f"[DEBUG] Получен ответ: status={response.status_code}")
            response.raise_for_status()
            data = response.json()
            
            print(f"[DEBUG] Response status: {response.status_code}")
            print(f"[DEBUG] Response data: {data}")
            
            if data.get("code") != "0":
                print(f"❌ Ошибка API OKX: {data.get('msg', 'Unknown error')}")
                return None
            
            instruments = data.get("data", [])
            print(f"✅ Получено {len(instruments)} торговых пар")
            
            # Фильтруем только активные пары
            active_pairs = [
                inst for inst in instruments 
                if inst.get("state") == "live"
            ]
            
            print(f"✅ Активных пар: {len(active_pairs)}")
            
            # Группируем по базовой валюте (quote currency)
            usdt_pairs = [s for s in active_pairs if s.get("quoteCcy") == "USDT"]
            usdc_pairs = [s for s in active_pairs if s.get("quoteCcy") == "USDC"]
            btc_pairs = [s for s in active_pairs if s.get("quoteCcy") == "BTC"]
            eth_pairs = [s for s in active_pairs if s.get("quoteCcy") == "ETH"]
            
            print(f"\n📊 Статистика по парам:")
            print(f"   USDT: {len(usdt_pairs)} пар")
            print(f"   USDC: {len(usdc_pairs)} пар")
            print(f"   BTC:  {len(btc_pairs)} пар")
            print(f"   ETH:  {len(eth_pairs)} пар")
            
            # Сохраняем все активные символы
            all_symbols = [s["instId"] for s in active_pairs]
            
            # Сохраняем только USDT пары (самые популярные)
            usdt_symbols = [s["instId"] for s in usdt_pairs]
            
            # Сохраняем в JSON с дополнительной информацией
            output_dir = Path(__file__).parent.parent
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 1. Все активные символы (простой список)
            all_symbols_file = output_dir / "okx_websocket_all_symbols.txt"
            with open(all_symbols_file, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(all_symbols)))
            print(f"\n💾 Сохранено: {all_symbols_file}")
            print(f"   Всего символов: {len(all_symbols)}")
            
            # 2. Только USDT пары (простой список)
            usdt_symbols_file = output_dir / "okx_websocket_usdt_symbols.txt"
            with open(usdt_symbols_file, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(usdt_symbols)))
            print(f"💾 Сохранено: {usdt_symbols_file}")
            print(f"   USDT пар: {len(usdt_symbols)}")
            
            # 3. Полная информация в JSON (только USDT)
            usdt_json_file = output_dir / "okx_websocket_usdt_pairs.json"
            usdt_data = {
                "timestamp": datetime.now().isoformat(),
                "total_pairs": len(usdt_pairs),
                "pairs": [
                    {
                        "instId": s["instId"],
                        "baseCcy": s.get("baseCcy", ""),
                        "quoteCcy": s.get("quoteCcy", ""),
                        "state": s.get("state", ""),
                    }
                    for s in sorted(usdt_pairs, key=lambda x: x["instId"])
                ]
            }
            with open(usdt_json_file, "w", encoding="utf-8") as f:
                json.dump(usdt_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Сохранено: {usdt_json_file}")
            
            # 4. Полная информация в JSON (все активные пары)
            all_json_file = output_dir / "okx_websocket_all_pairs.json"
            all_data = {
                "timestamp": datetime.now().isoformat(),
                "total_pairs": len(active_pairs),
                "pairs_by_quote": {
                    "USDT": len(usdt_pairs),
                    "USDC": len(usdc_pairs),
                    "BTC": len(btc_pairs),
                    "ETH": len(eth_pairs),
                },
                "pairs": [
                    {
                        "instId": s["instId"],
                        "baseCcy": s.get("baseCcy", ""),
                        "quoteCcy": s.get("quoteCcy", ""),
                        "state": s.get("state", ""),
                    }
                    for s in sorted(active_pairs, key=lambda x: (x.get("quoteCcy", ""), x["instId"]))
                ]
            }
            with open(all_json_file, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Сохранено: {all_json_file}")
            
            print(f"\n✅ Готово! Все файлы сохранены в: {output_dir}")
            print(f"\n📝 Формат символов для WebSocket:")
            print(f"   Пример: BTC-USDT, ETH-USDT, SOL-USDT")
            print(f"   WebSocket URL: wss://ws.okx.com:8443/ws/v5/public")
            print(f"   Канал: tickers (нужно подписаться на каждый тикер отдельно)")
            
            return {
                "all_symbols": all_symbols,
                "usdt_symbols": usdt_symbols,
                "usdt_pairs": usdt_pairs,
                "all_pairs": active_pairs,
            }
            
        except httpx.HTTPError as e:
            print(f"❌ Ошибка HTTP: {e}")
            print(f"   URL: {url}")
            print(f"   Параметры: instType=SPOT")
            import traceback
            traceback.print_exc()
            return None
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return None


if __name__ == "__main__":
    result = asyncio.run(get_okx_coins())
    if result:
        print(f"\n🎯 Краткая сводка:")
        print(f"   Всего символов: {len(result['all_symbols'])}")
        print(f"   USDT пар: {len(result['usdt_symbols'])}")
        print(f"\n💡 Для использования в WebSocket используйте символы из файлов:")
        print(f"   - okx_websocket_usdt_symbols.txt (только USDT пары)")
        print(f"   - okx_websocket_all_symbols.txt (все пары)")

