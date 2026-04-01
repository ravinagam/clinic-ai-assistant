import asyncio
import logging
import re
from datetime import datetime
from functools import partial
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


# ── Startup diagnostics ───────────────────────────────────────────────────────

def log_notification_config():
    """Called at startup to surface missing config early."""
    if settings.twilio_whatsapp_from and settings.twilio_account_sid:
        logger.info(
            f"WhatsApp notifications ENABLED — from: {settings.twilio_whatsapp_from}. "
            "NOTE: Twilio sandbox recipients must first send 'join <keyword>' "
            f"to {settings.twilio_whatsapp_from.replace('whatsapp:', '')}."
        )
    elif settings.twilio_account_sid and settings.twilio_from_number:
        logger.info(f"SMS notifications ENABLED — from: {settings.twilio_from_number}")
    else:
        logger.warning(
            "Twilio NOT configured — SMS/WhatsApp notifications are DISABLED. "
            "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM in .env"
        )

    if not settings.resend_api_key or settings.resend_api_key.startswith("re_xxx"):
        logger.warning("Resend NOT configured — email notifications are DISABLED.")


# ── Phone normalization ───────────────────────────────────────────────────────

def normalize_phone(phone: str) -> str:
    """
    Normalize to E.164. Defaults to +91 (India) for 10-digit numbers.
    Examples: 8519858590 → +918519858590, 08519858590 → +918519858590
    """
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 11:
        return f"+91{digits[1:]}"
    if len(digits) == 10:
        return f"+91{digits}"
    # Already has country code
    return f"+{digits}" if not phone.startswith("+") else phone


# ── Email via Resend ──────────────────────────────────────────────────────────

async def send_email(to: str, subject: str, html: str) -> bool:
    if not settings.resend_api_key or settings.resend_api_key.startswith("re_xxx") or not to:
        logger.info(f"Email skipped — no valid Resend API key. Subject: {subject}")
        return False
    try:
        import resend
        resend.api_key = settings.resend_api_key

        def _send():
            return resend.Emails.send({
                "from": settings.email_from,
                "to": to,
                "subject": subject,
                "html": html,
            })

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send)
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to}: {e}")
        return False


# ── WhatsApp via Twilio ───────────────────────────────────────────────────────

async def send_whatsapp(to: str, body: str) -> bool:
    if not settings.twilio_account_sid or not settings.twilio_whatsapp_from:
        logger.info("WhatsApp skipped — TWILIO_WHATSAPP_FROM not configured.")
        return False
    if not to:
        logger.warning("WhatsApp skipped — recipient phone number is empty.")
        return False

    normalized = normalize_phone(to)
    wa_to = f"whatsapp:{normalized}"
    wa_from = settings.twilio_whatsapp_from
    if not wa_from.startswith("whatsapp:"):
        wa_from = f"whatsapp:{wa_from}"

    logger.info(f"Sending WhatsApp: from={wa_from} to={wa_to}")

    def _send():
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        msg = client.messages.create(to=wa_to, from_=wa_from, body=body)
        return msg.sid

    try:
        loop = asyncio.get_event_loop()
        sid = await loop.run_in_executor(None, _send)
        logger.info(f"WhatsApp sent to {normalized} — SID: {sid}")
        return True
    except Exception as e:
        logger.error(
            f"WhatsApp FAILED to {normalized}: {e}\n"
            "Common causes:\n"
            "  1. Recipient has NOT joined the Twilio sandbox "
            f"(they must WhatsApp '{settings.twilio_whatsapp_from.replace('whatsapp:','')}' with 'join <keyword>')\n"
            "  2. Wrong TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN\n"
            "  3. TWILIO_WHATSAPP_FROM format should be 'whatsapp:+1XXXXXXXXXX'"
        )
        return False


# ── SMS via Twilio ────────────────────────────────────────────────────────────

async def send_sms(to: str, body: str) -> bool:
    if not settings.twilio_account_sid or not settings.twilio_from_number:
        logger.info("SMS skipped — Twilio SMS not configured.")
        return False
    if not to:
        logger.warning("SMS skipped — recipient phone number is empty.")
        return False

    normalized = normalize_phone(to)
    logger.info(f"Sending SMS: from={settings.twilio_from_number} to={normalized}")

    def _send():
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        msg = client.messages.create(to=normalized, from_=settings.twilio_from_number, body=body)
        return msg.sid

    try:
        loop = asyncio.get_event_loop()
        sid = await loop.run_in_executor(None, _send)
        logger.info(f"SMS sent to {normalized} — SID: {sid}")
        return True
    except Exception as e:
        logger.error(f"SMS FAILED to {normalized}: {e}")
        return False


# ── Notification templates ────────────────────────────────────────────────────

def _format_dt(dt: datetime) -> str:
    return dt.strftime("%A, %d %b %Y at %I:%M %p")


async def send_booking_confirmation(
    patient_name: str,
    patient_phone: str,
    patient_email: Optional[str],
    doctor_name: str,
    scheduled_at: datetime,
    appointment_id: int,
    channel: str = "web",
) -> None:
    dt_str = _format_dt(scheduled_at)
    clinic = settings.clinic_name

    message_body = (
        f"Hi {patient_name}! Your appointment is confirmed ✓\n"
        f"Clinic: {clinic}\n"
        f"Doctor: Dr. {doctor_name}\n"
        f"When: {dt_str}\n"
        f"Ref: #{appointment_id}\n"
        f"To reschedule call: {settings.clinic_phone}"
    )

    email_html = f"""
    <h2>Appointment Confirmed ✓</h2>
    <p>Hi <strong>{patient_name}</strong>,</p>
    <table cellpadding="8" style="border-collapse:collapse">
      <tr><td><b>Clinic</b></td><td>{clinic}</td></tr>
      <tr><td><b>Doctor</b></td><td>Dr. {doctor_name}</td></tr>
      <tr><td><b>Date &amp; Time</b></td><td>{dt_str}</td></tr>
      <tr><td><b>Reference</b></td><td>#{appointment_id}</td></tr>
    </table>
    <p>📍 {settings.clinic_address}</p>
    <p>To reschedule: <a href="tel:{settings.clinic_phone}">{settings.clinic_phone}</a></p>
    """

    # WhatsApp always takes priority (works for all channels)
    notified = False
    if settings.twilio_whatsapp_from:
        notified = await send_whatsapp(patient_phone, message_body)

    # Fall back to SMS if WhatsApp not sent
    if not notified and settings.twilio_account_sid and settings.twilio_from_number:
        notified = await send_sms(patient_phone, message_body)

    if not notified:
        logger.warning(
            f"Appointment #{appointment_id} confirmed but NO notification sent to {patient_phone}. "
            "Configure Twilio credentials in .env to enable WhatsApp/SMS."
        )

    if patient_email:
        await send_email(patient_email, f"Appointment Confirmed — {clinic}", email_html)


async def send_appointment_reminder(
    patient_name: str,
    patient_phone: str,
    patient_email: Optional[str],
    doctor_name: str,
    scheduled_at: datetime,
    appointment_id: int,
) -> None:
    dt_str = _format_dt(scheduled_at)
    clinic = settings.clinic_name

    message_body = (
        f"Reminder: Hi {patient_name}!\n"
        f"You have an appointment tomorrow at {clinic}.\n"
        f"Doctor: Dr. {doctor_name}\n"
        f"Time: {scheduled_at.strftime('%I:%M %p')}\n"
        f"Ref: #{appointment_id}\n"
        f"Call {settings.clinic_phone} to reschedule."
    )

    email_html = f"""
    <h2>Appointment Reminder</h2>
    <p>Hi <strong>{patient_name}</strong>, reminder for tomorrow:</p>
    <table cellpadding="8" style="border-collapse:collapse">
      <tr><td><b>Doctor</b></td><td>Dr. {doctor_name}</td></tr>
      <tr><td><b>When</b></td><td>{dt_str}</td></tr>
      <tr><td><b>Where</b></td><td>{settings.clinic_address}</td></tr>
    </table>
    """

    if settings.twilio_whatsapp_from:
        await send_whatsapp(patient_phone, message_body)
    elif settings.twilio_account_sid:
        await send_sms(patient_phone, message_body)

    if patient_email:
        await send_email(patient_email, f"Reminder: Appointment Tomorrow — {clinic}", email_html)
