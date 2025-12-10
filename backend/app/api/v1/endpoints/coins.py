from typing import List
from fastapi import APIRouter, HTTPException, Body

from app.services.coingecko import CoinGeckoService

router = APIRouter()


@router.get("/list")
async def get_coins_list(
    limit: int = 100,
    start: int = 1,
    force_refresh: bool = False,
):
    """Получить список криптовалют"""
    print(f"\n[API Endpoint] GET /coins/list - limit={limit}, start={start}, force_refresh={force_refresh}")
    service = CoinGeckoService()
    try:
        coins = await service.get_crypto_list(limit=limit, page=start, force_refresh=force_refresh)
        print(f"[API Endpoint] Возвращаем {len(coins)} монет клиенту")
        return {"data": coins}
    except Exception as e:
        print(f"[API Endpoint] Ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list/static")
async def get_coins_list_static(
    limit: int = 100,
    start: int = 1,
    force_refresh: bool = False,
):
    """Получить только статические данные монет (id, name, symbol, imageUrl) без цен - для быстрой загрузки"""
    print(f"\n[API Endpoint] GET /coins/list/static - limit={limit}, start={start}, force_refresh={force_refresh}")
    service = CoinGeckoService()
    try:
        coins = await service.get_crypto_list_static_only(limit=limit, page=start, force_refresh=force_refresh)
        print(f"[API Endpoint] Возвращаем {len(coins)} монет со статическими данными клиенту")
        return {"data": coins}
    except Exception as e:
        print(f"[API Endpoint] Ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/list/prices")
async def get_coins_list_prices(coin_ids: List[str] = Body(...)):
    """Получить только цены для списка монет - для обновления после загрузки статики"""
    print(f"\n[API Endpoint] POST /coins/list/prices - запрошено цен для {len(coin_ids)} монет")
    service = CoinGeckoService()
    try:
        prices = await service.get_crypto_list_prices(coin_ids)
        print(f"[API Endpoint] Возвращаем цены для {len(prices)} монет клиенту")
        return {"data": prices}
    except Exception as e:
        print(f"[API Endpoint] Ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{coin_id}")
async def get_coin_details(
    coin_id: str,
):
    """Получить детали криптовалюты"""
    print(f"\n[API Endpoint] GET /coins/{coin_id}")
    service = CoinGeckoService()
    try:
        coin = await service.get_crypto_details(coin_id)
        print(f"[API Endpoint] Возвращаем данные монеты клиенту: {coin}")
        return {"data": coin}
    except Exception as e:
        print(f"[API Endpoint] Ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{coin_id}/chart")
async def get_coin_chart(
    coin_id: str,
    period: str = "7d",  # 1d, 7d, 30d, 1y
):
    """Получить данные графика для криптовалюты"""
    print(f"\n[API Endpoint] GET /coins/{coin_id}/chart - period={period}")
    service = CoinGeckoService()
    try:
        chart_data = await service.get_crypto_chart(coin_id, period)
        print(f"[API Endpoint] Возвращаем {len(chart_data)} точек графика клиенту")
        return {"data": chart_data}
    except Exception as e:
        print(f"[API Endpoint] Ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

