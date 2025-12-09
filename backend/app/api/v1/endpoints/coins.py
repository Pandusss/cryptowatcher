from fastapi import APIRouter, HTTPException

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

