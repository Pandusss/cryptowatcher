from typing import List
from fastapi import APIRouter, HTTPException, Body

from app.services.coin_service import CoinService
import logging

router = APIRouter()
logger = logging.getLogger("EndpointsCoins")



@router.get("/list")
async def get_coins_list(
    limit: int = 100,
    start: int = 1,
    force_refresh: bool = False,
):
    """Get a list of cryptocurrencies"""
    service = CoinService()
    try:
        coins = await service.get_crypto_list(limit=limit, page=start, force_refresh=force_refresh)
        logger.info(f"Returning {len(coins)} coins to the client")
        return {"data": coins}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list/static")
async def get_coins_list_static(
    limit: int = 100,
    start: int = 1,
    force_refresh: bool = False,
):
    """Get a list of coins (static + prices from cache) - for fast loading"""
    service = CoinService()
    try:
        # Используем единый метод get_crypto_list (объединена логика с get_crypto_list_static_only)
        coins = await service.get_crypto_list(limit=limit, page=start, force_refresh=force_refresh)
        logger.info(f"Returning {len(coins)} coins to the client")
        return {"data": coins}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/list/prices")
async def get_coins_list_prices(coin_ids: List[str] = Body(...)):
    """Получить только цены для списка монет - для обновления после загрузки статики"""
    service = CoinService()
    try:
        prices = await service.get_crypto_list_prices(coin_ids)
        logger.info(f"Returning prices for {len(prices)} coins to the client")
        return {"data": prices}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{coin_id}")
async def get_coin_details(
    coin_id: str,
):
    """Получить детали криптовалюты"""
    service = CoinService()
    try:
        coin = await service.get_crypto_details(coin_id)
        logger.info(f"Returning these coins to the client: {coin}")
        return {"data": coin}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{coin_id}/chart")
async def get_coin_chart(
    coin_id: str,
    period: str = "7d",  # 1d, 7d, 30d, 1y
):
    """Получить данные графика для криптовалюты с учетом приоритетов провайдеров"""
    from app.services.aggregation_service import aggregation_service
    try:
        chart_data = await aggregation_service.get_coin_chart(coin_id, period)
        if chart_data:
            logger.info(f"Returning {len(chart_data)} graph points to the client")
            return {"data": chart_data}
        else:
            logger.warning(f"Chart not found for {coin_id}")
            return {"data": []}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
