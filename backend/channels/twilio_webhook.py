"""
Twilio webhook handler for SMS and WhatsApp channels.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from reception.bot import reception_bot
from appointments.engine import (
    book_appointment, get_first_available_doctor, get_best_doctor,
)
from appointments.models import Channel, Conversation
from notifications.service import send_booking_confirmation
from channels.datetime_parser import parse_preferred_datetime
from channels.web_api import find_best_slot
from config import settings

router = APIRouter(prefix="/twilio", tags=["Twilio"])


def twiml_response(message: str) -> Response:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response><Message>{message}</Message></Response>"""
    return Response(content=xml, media_type="application/xml")


@router.post("/webhook")
async def twilio_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    incoming_msg: str = form.get("Body", "").strip()
    from_number: str = form.get("From", "")
    channel_raw: str = form.get("To", "")

    channel = Channel.whatsapp if "whatsapp" in channel_raw.lower() else Channel.sms
    session_id = f"twilio:{from_number}"

    bot_response = await reception_bot.chat(
        message=incoming_msg,
        session_id=session_id,
        channel=channel.value,
    )

    # Persist conversation
    result = await db.execute(
        select(Conversation).where(Conversation.session_id == session_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        conv = Conversation(
            session_id=session_id,
            channel=channel,
            patient_phone=from_number.replace("whatsapp:", ""),
        )
        db.add(conv)
    from reception.session import session_manager
    conv.messages = await session_manager.get_history(session_id)
    await db.commit()

    reply_text = bot_response.message

    if bot_response.booking_intent:
        intent = bot_response.booking_intent
        try:
            doctor = await get_best_doctor(db, intent.get("reason", ""))
            if not doctor:
                reply_text += "\n\nNo doctors configured. Please call us."
            else:
                preferred_dt = parse_preferred_datetime(intent.get("preferred_datetime", ""))
                slot = await find_best_slot(db, doctor.id, preferred_dt)
                if not slot:
                    reply_text += "\n\nNo open slots in the next 2 weeks. Our team will call you."
                else:
                    appointment = await book_appointment(
                        db=db,
                        patient_name=intent["name"],
                        patient_phone=from_number.replace("whatsapp:", ""),
                        doctor_id=doctor.id,
                        scheduled_at=slot,
                        reason=intent.get("reason", "General Consultation"),
                        channel=channel,
                        session_id=session_id,
                    )
                    await send_booking_confirmation(
                        patient_name=intent["name"],
                        patient_phone=from_number.replace("whatsapp:", ""),
                        patient_email=None,
                        doctor_name=doctor.name,
                        scheduled_at=slot,
                        appointment_id=appointment.id,
                        channel=channel.value,
                    )
                    slot_str = slot.strftime("%A, %d %b at %I:%M %p")
                    reply_text += f"\n\n✅ Appointment #{appointment.id} confirmed for {slot_str}!"
        except ValueError as e:
            reply_text += f"\n\n⚠️ {e}"

    return twiml_response(reply_text)
