"""
Optional Google Calendar integration.
Falls back gracefully if credentials are not configured.
"""
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


def _build_service(token: str, refresh_token: str):
    if not GOOGLE_AVAILABLE:
        raise RuntimeError("google-api-python-client is not installed.")
    from config import settings
    creds = Credentials(
        token=token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    return build("calendar", "v3", credentials=creds)


async def create_calendar_event(
    calendar_id: str,
    token: str,
    refresh_token: str,
    summary: str,
    start_dt: datetime,
    duration_minutes: int = 20,
    description: str = "",
    attendee_email: Optional[str] = None,
) -> Optional[str]:
    """Create a Google Calendar event. Returns event ID or None on failure."""
    if not GOOGLE_AVAILABLE or not token:
        logger.info("Google Calendar not configured — skipping event creation.")
        return None

    try:
        service = _build_service(token, refresh_token)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Kolkata"},
        }
        if attendee_email:
            event["attendees"] = [{"email": attendee_email}]

        created = service.events().insert(calendarId=calendar_id, body=event).execute()
        return created.get("id")
    except Exception as e:
        logger.error(f"Google Calendar event creation failed: {e}")
        return None
