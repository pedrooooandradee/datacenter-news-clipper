from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def format_datetime_br(dt: datetime) -> str:
    """
    Converts a datetime object to Brazilian timezone (America/Sao_Paulo) 
    and returns it with day and 3-letter month abbreviation in Portuguese.
    
    Args:
        dt: datetime object (naive or with timezone)
        
    Returns:
        str: Formatted date string in Brazilian timezone (e.g. "23 abr")
    """
    # Portuguese month abbreviations
    PT_MONTHS = {
        1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
    }
    # If datetime is naive (no timezone), assume it's UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Convert to Brazilian timezone
    br_dt = dt.astimezone(ZoneInfo("America/Sao_Paulo"))
    
    # Format with day and Portuguese month abbreviation
    day = br_dt.day
    month_abbr = PT_MONTHS[br_dt.month]
    return f"{day:02d} {month_abbr}"
