"""
Natural language + ISO datetime parser for patient-provided preferred times.
"""
import re
from datetime import datetime, date, time, timedelta
from typing import Optional


DAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

TIME_OF_DAY = {
    "morning": 9,
    "afternoon": 14,
    "evening": 17,
    "noon": 12,
}


def _parse_time(text: str) -> tuple[int, int]:
    """Extract (hour, minute) from text. Defaults to 9:00."""
    for name, hour in TIME_OF_DAY.items():
        if name in text:
            return hour, 0

    match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text, re.IGNORECASE)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        ampm = (match.group(3) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        elif not ampm and 1 <= hour <= 6:
            hour += 12  # ambiguous — assume PM for clinic hours
        return min(hour, 23), min(minute, 59)

    return 9, 0


def parse_preferred_datetime(text: str) -> Optional[datetime]:
    """
    Parse datetime from ISO string or natural language.
    Returns None if completely unparseable.
    """
    if not text:
        return None

    # ISO first
    try:
        return datetime.fromisoformat(text)
    except (ValueError, TypeError):
        pass

    text_lower = text.lower().strip()
    hour, minute = _parse_time(text_lower)
    today = datetime.now()

    # Specific date: "1st April 2026", "April 1", "1 April", "01/04/2026"
    month_found = None
    for name, num in MONTHS.items():
        if name in text_lower:
            month_found = num
            break

    if month_found:
        day_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', text_lower)
        if day_match:
            day_num = int(day_match.group(1))
            year_match = re.search(r'\b(20\d{2})\b', text_lower)
            year = int(year_match.group(1)) if year_match else today.year
            try:
                target_date = date(year, month_found, day_num)
                return datetime.combine(target_date, time(hour, minute))
            except ValueError:
                pass

    # DD/MM/YYYY or MM/DD/YYYY
    slash_match = re.search(r'(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?', text_lower)
    if slash_match:
        d1, d2 = int(slash_match.group(1)), int(slash_match.group(2))
        yr = int(slash_match.group(3) or today.year)
        if yr < 100:
            yr += 2000
        try:
            # Try DD/MM first (Indian format)
            target_date = date(yr, d2, d1)
            return datetime.combine(target_date, time(hour, minute))
        except ValueError:
            try:
                target_date = date(yr, d1, d2)
                return datetime.combine(target_date, time(hour, minute))
            except ValueError:
                pass

    # Named weekday → next occurrence
    for name, weekday in DAY_NAMES.items():
        if re.search(rf'\b{name}\b', text_lower):
            days_ahead = (weekday - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            target_date = (today + timedelta(days=days_ahead)).date()
            return datetime.combine(target_date, time(hour, minute))

    # Relative
    if "today" in text_lower:
        return datetime.combine(today.date(), time(hour, minute))
    if "tomorrow" in text_lower:
        return datetime.combine((today + timedelta(days=1)).date(), time(hour, minute))

    return None
