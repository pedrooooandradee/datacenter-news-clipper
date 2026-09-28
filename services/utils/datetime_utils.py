from datetime import date, datetime, timezone
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


def dia_local(dt: datetime) -> date:
    """
    The civil day of an instant on this computer's calendar.

    The edition's window, its archive folder and its PDF header are all counted
    on the computer's own calendar. Dates from the feed and from the pages carry
    their own offsets (GMT, -03:00, +00:00), and taking .date() of each as it
    came compared one calendar against another: a Google News entry stamped
    01:00 GMT on the 29th is the evening of the 28th in Brasília.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().date()
