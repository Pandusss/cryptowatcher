"""
Utilities for formatting data
"""
from typing import Union
from datetime import datetime, timezone

def get_price_decimals(price: Union[float, int]) -> int:
    """
    Determine the number of decimal places for the price
    
    Args:
        price: The price of the coin
        
    Returns:
        Number of decimal places (2, 4, 6 or 8)
    """
    if price >= 1:
        return 2
    elif price >= 0.01:
        return 4
    elif price >= 0.0001:
        return 6
    else:
        return 8


def format_chart_date(date_obj: datetime, period: str) -> str:
    """
    Format the date for the chart.
    Returns an ISO string with the UTC time zone for correct parsing on the frontend.
    Example: "2025-12-17T18:12:12+00:00"
    """
    from datetime import timezone, datetime
    
    # 1. Ensure datetime is in UTC
    if date_obj.tzinfo is None:
        # If datetime has no timezone - assume it's already UTC
        date_obj_utc = date_obj.replace(tzinfo=timezone.utc)
    else:
        # If there is a timezone - convert to UTC
        date_obj_utc = date_obj.astimezone(timezone.utc)
    
    # 2. Format as ISO string with UTC timezone
    # For periods 1d and 7d include time
    if period in ("1d", "7d"):
        # ISO format with timezone: "2025-12-17T18:12:12+00:00"
        return date_obj_utc.isoformat()
    else:
        # For longer periods use only date with 00:00 time
        date_only = date_obj_utc.date()
        # Create datetime with 00:00:00 time in UTC
        date_with_time = datetime.combine(date_only, datetime.min.time(), tzinfo=timezone.utc)
        return date_with_time.isoformat()