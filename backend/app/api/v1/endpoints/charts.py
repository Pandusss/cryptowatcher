"""
Chart image endpoints
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import logging

from app.services.chart_storage import chart_storage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/charts/{chart_id}")
async def get_chart_image(chart_id: str):
    """
    Get chart image by ID
    
    Returns PNG image
    """
    try:
        image_bytes = chart_storage.get_chart(chart_id)
        
        if not image_bytes:
            raise HTTPException(status_code=404, detail="Chart not found or expired")
        
        return Response(
            content=image_bytes,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=3600",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chart {chart_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

